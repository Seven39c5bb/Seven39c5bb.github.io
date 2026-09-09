import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path


EXPECTED_REMOTE = "https://github.com/Seven39c5bb/Seven39c5bb.github.io.git"
BRANCH = "main"
PUBLIC_ROOTS = {"2025", "about", "archives", "categories", "comments", "content", "css", "games", "img", "js", "link", "live2dw", "movies", "music", "projects", "scripts", "tags"}
PUBLIC_FILES = {"index.html", "search.xml", ".gitignore", "BLOG-MANAGER.md", "manage-blog.cmd"}
EXTENSIONS = {".html", ".css", ".js", ".json", ".xml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".mp3", ".ogg", ".wav", ".mp4", ".webm", ".woff", ".woff2", ".ttf", ".eot", ".moc", ".py", ".md", ".cmd", ".pdf"}


class CloudSync:
    def __init__(self, root):
        self.root = root
        self.pending = None

    def git(self, *arguments, check=True):
        environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never", "GIT_LITERAL_PATHSPECS": "1"}
        try:
            result = subprocess.run(["git", "-c", "core.quotepath=false", *arguments], cwd=self.root,
                                    env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Git 未安装、请求超时或网络不可用。请在终端确认 GitHub 登录后重试。") from error
        if check and result.returncode:
            message = result.stderr.decode("utf-8", errors="replace")[-2500:]
            message = re.sub(r"https://[^\s/@]+:[^\s/@]+@", "https://[redacted]@", message)
            raise ValueError("Git 操作失败（未强制覆盖远端）：" + message)
        return result

    def text(self, *arguments):
        return self.git(*arguments).stdout.decode("utf-8", errors="replace").strip()

    def verify_target(self):
        if self.text("branch", "--show-current") != BRANCH:
            raise ValueError("请先切换到 main 分支；工作台不会替你切换分支")
        if self.text("remote", "get-url", "--all", "origin") != EXPECTED_REMOTE or self.text("remote", "get-url", "--push", "--all", "origin") != EXPECTED_REMOTE:
            raise ValueError("origin 地址与当前博客仓库不一致，已停止同步")
        if self.text("diff", "--name-only", "--cached"):
            raise ValueError("Git 暂存区已有改动，请先自行提交或取消暂存，再使用工作台同步")
        for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
            if Path(self.text("rev-parse", "--git-path", name)).is_absolute():
                path = Path(self.text("rev-parse", "--git-path", name))
            else:
                path = self.root / self.text("rev-parse", "--git-path", name)
            if path.exists():
                raise ValueError("Git 正在合并或变基，请先在终端完成该操作")

    def allowed(self, name):
        path = Path(name)
        if name in PUBLIC_FILES:
            return True
        if not path.parts or path.parts[0] not in PUBLIC_ROOTS or path.suffix.lower() not in EXTENSIONS:
            return False
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            return False
        resolved = (self.root / path).resolve()
        return resolved.is_relative_to(self.root.resolve()) and not any(part.startswith(".") for part in resolved.relative_to(self.root.resolve()).parts)

    def changes(self):
        raw = self.git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames").stdout
        selected, excluded = [], []
        for line in raw.split(b"\0"):
            if not line:
                continue
            name = line[3:].decode("utf-8")
            item = {"path": name, "status": line[:2].decode("ascii")}
            if not self.allowed(name):
                excluded.append(item)
                continue
            path = self.root / name
            if path.is_symlink():
                raise ValueError("发布列表包含符号链接，请先人工检查：" + name)
            item["revision"] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            item["size"] = path.stat().st_size if path.is_file() else 0
            if item["size"] >= 95 * 1024 * 1024:
                raise ValueError("文件过大，请先使用适当的资源托管方式：" + name)
            selected.append(item)
        return selected, excluded

    def inspect(self, fetch=False):
        self.verify_target()
        if fetch:
            self.git("fetch", "--no-tags", "origin", BRANCH)
            remote = self.text("rev-parse", "FETCH_HEAD")
        else:
            result = self.git("rev-parse", "--verify", "refs/remotes/origin/" + BRANCH, check=False)
            remote = result.stdout.decode().strip() if result.returncode == 0 else None
        head = self.text("rev-parse", "HEAD")
        changes, excluded = self.changes()
        behind = bool(remote and self.git("merge-base", "--is-ancestor", remote, head, check=False).returncode)
        commits = self.text("log", "--format=%h %s", f"{remote}..HEAD").splitlines() if remote else []
        return {"head": head, "remote_head": remote, "remote": EXPECTED_REMOTE, "branch": BRANCH,
                "changes": changes, "excluded": excluded, "commits": commits, "behind": behind}

    def fingerprint(self, state):
        return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()

    def prepare(self):
        self.pending = None
        state = self.inspect(fetch=True)
        if state["behind"]:
            raise ValueError("云端存在本地未包含的提交。请先在 Git 工具中拉取并解决冲突，然后重新检查；工作台不会自动覆盖或强推")
        ticket = secrets.token_urlsafe(24)
        self.pending = (ticket, self.fingerprint(state), time.monotonic())
        return {**state, "ticket": ticket}

    def publish(self, ticket):
        pending = self.pending
        self.pending = None
        if not pending or not isinstance(ticket, str) or not secrets.compare_digest(ticket, pending[0]) or time.monotonic() - pending[2] > 600:
            raise ValueError("发布确认已过期，请重新检查变更")
        state = self.inspect(fetch=True)
        if self.fingerprint(state) != pending[1]:
            raise ValueError("本地文件或远端版本已变化，请重新检查并确认发布列表")
        names = [item["path"] for item in state["changes"]]
        if names:
            self.git("add", "-A", "--", *names)
            try:
                staged = self.git("diff", "--cached", "--name-only", "-z").stdout.decode("utf-8").strip("\0").split("\0")
                staged = [name for name in staged if name]
                if not set(staged).issubset(set(names)):
                    raise ValueError("暂存区与确认列表不一致，已取消提交")
                if staged:
                    self.git("commit", "-m", "Update blog from local studio")
            except Exception:
                self.git("reset", "--quiet", "HEAD", "--", *names, check=False)
                raise
        commit = self.text("rev-parse", "HEAD")
        try:
            self.git("push", "--no-follow-tags", "--recurse-submodules=no", "origin", "HEAD:refs/heads/" + BRANCH)
        except ValueError as error:
            raise ValueError("本地提交已保留，但推送未完成。修复网络或 GitHub 登录后，重新检查再推送即可，不需要重复编辑。\n" + str(error)) from error
        return {"commit": commit, "message": "已推送 GitHub main 分支。GitHub Pages 是否部署成功需在仓库 Actions / Pages 中确认。"}
