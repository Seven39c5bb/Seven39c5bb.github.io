import argparse
import base64
import hashlib
import io
import json
import mimetypes
import re
import secrets
import shutil
import socket
import threading
import webbrowser
import zipfile
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

import build_games
import build_about
import build_projects
import build_appearance
import build_site
from cloud_sync import CloudSync


ROOT = build_games.ROOT
PRIVATE = ROOT / ".blog-manager"
UI = ROOT / "scripts/manager"
LOCK = threading.RLock()
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


def backend_revision():
    return hashlib.sha256(b"".join(path.read_bytes() for path in sorted(Path(__file__).parent.glob("*.py")))).hexdigest()


BACKEND_REVISION = backend_revision()
WORKSPACE_ID = hashlib.sha256(str(ROOT.resolve()).encode("utf-8")).hexdigest()


class ManagerServer(ThreadingHTTPServer):
    allow_reuse_address = False
    allow_reuse_port = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def folder(status):
    if status not in ("published", "draft", "trash"):
        raise ValueError("未知的文章状态")
    return ROOT / "content/games" if status == "published" else PRIVATE / status


def record_path(slug, status):
    if not isinstance(slug, str) or not SLUG.fullmatch(slug) or len(slug) > 100:
        raise ValueError("文章路径只能包含小写英文字母、数字和单个连字符")
    if slug in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[0-9]", slug):
        raise ValueError("该路径是 Windows 保留名称，请换一个")
    path = folder(status) / (slug + ".json")
    if not path.resolve().is_relative_to(folder(status).resolve()):
        raise ValueError("文章文件不能指向内容目录之外")
    return path


def revision(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def snapshot(path):
    if path.is_file():
        target = PRIVATE / "history" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + path.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def image_path(value):
    if not isinstance(value, str) or not value.startswith("/img/") or any(char in value for char in '<>"\'?#\\'):
        raise ValueError("图片必须是 /img/ 下的本地文件")
    path = (ROOT / value.lstrip("/")).resolve()
    if not path.is_relative_to((ROOT / "img").resolve()) or not path.is_file() or path.suffix.lower() not in IMAGE_TYPES:
        raise ValueError("图片文件不存在或格式不支持：" + value)
    return path


def validate(record, status):
    record_path(record.get("slug"), status)
    for field in ("title", "body", "cover", "imported", "source_updated", "source_id"):
        if not isinstance(record.get(field), str):
            raise ValueError("缺少字段：" + field)
    if not record["title"].strip() or len(record["title"]) > 180:
        raise ValueError("请输入标题（不超过 180 字）")
    date.fromisoformat(record["imported"])
    datetime.fromisoformat(record["source_updated"].replace("Z", "+00:00"))
    if status == "published":
        image_path(record["cover"])
        if not record["body"].strip():
            raise ValueError("发布前请填写正文")
        for reference in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", record["body"]):
            image_path(reference)
            if not reference.startswith("/img/games/"):
                raise ValueError("正文配图请使用 /img/games/ 下的图片")
        rating = float(build_games.score(record))
        if not 0 <= rating <= 10:
            raise ValueError("评分需要在 0 到 10 之间，请在正文写入 游戏评分：8")
        build_games.excerpt(record)


def list_records():
    records = []
    for status in ("published", "draft", "trash"):
        for path in folder(status).glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            records.append({**record, "status": status, "revision": revision(path)})
    return sorted(records, key=lambda record: record["source_updated"], reverse=True)


def studio_state():
    return {"projects": build_projects.load_projects(ROOT),
            "projects_revision": revision(ROOT / "content/projects.json"),
            "about": build_about.read_about(ROOT), "about_revision": revision(ROOT / "content/about.json"),
            "appearance": build_appearance.read_appearance(ROOT),
            "appearance_defaults": build_appearance.DEFAULT,
            "appearance_revision": revision(ROOT / "content/appearance.json"),
            "site": build_site.read_site(ROOT), "site_revision": revision(ROOT / "content/site.json")}


def save_document(kind, payload):
    if kind not in ("projects", "about", "appearance", "site"):
        raise ValueError("未知的资料类型")
    path = ROOT / f"content/{kind}.json"
    if revision(path) != payload.get("revision"):
        raise ValueError("资料已被其他窗口修改，请刷新页面后重新编辑")
    record = payload["record"]
    if kind == "site":
        record = build_site.validate(record, ROOT)
    elif kind == "appearance":
        record = build_appearance.validate(record)
    elif kind == "about":
        build_about.validate_about(record, ROOT)
    elif not isinstance(record, list) or len(record) > 200:
        raise ValueError("游戏作品必须是列表，最多 200 个")
    original = path.read_bytes() if path.exists() else None
    snapshot(path)
    try:
        atomic_write(path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if kind == "projects":
            for project in build_projects.load_projects(ROOT):
                build_projects.project_card(project, ROOT)
        changed = generate()
    except Exception:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, original)
        raise
    return {"changed": len(changed), "revision": revision(path)}


def generate():
    for record in list_records():
        if record["status"] == "published":
            validate(record, "published")
    outputs = build_games.build()
    changed = []
    obsolete = build_games.obsolete_pages(outputs)
    originals = {}
    try:
        for name, text in outputs.items():
            path = ROOT / name
            if path.exists() and path.read_text(encoding="utf-8") == text:
                continue
            originals[path] = path.read_bytes() if path.exists() else None
            atomic_write(path, text.encode("utf-8"))
            changed.append(name)
        for path in obsolete:
            originals[path] = path.read_bytes()
            path.unlink()
            changed.append(path.relative_to(ROOT).as_posix())
    except Exception:
        for path, data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, data)
        raise
    return changed


def save_record(payload):
    status = payload.get("status", "draft")
    if status == "trash":
        raise ValueError("请先恢复回收站文章")
    record = payload["record"]
    validate(record, status)
    destination = record_path(record["slug"], status)
    previous_status = payload.get("previous_status")
    source = record_path(record["slug"], previous_status) if previous_status else destination
    if previous_status and (not source.exists() or revision(source) != payload.get("revision")):
        raise ValueError("文章已被其他窗口修改，请刷新后重新打开")
    for other in ("published", "draft", "trash"):
        candidate = record_path(record["slug"], other)
        if candidate.exists() and (not previous_status or candidate != source):
            raise ValueError("这个文章路径已存在，请更换路径")
    original = source.read_bytes() if source.exists() else None
    snapshot(source)
    try:
        atomic_write(destination, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if source != destination:
            source.unlink()
        changed = generate() if "published" in (status, previous_status) else []
    except Exception:
        destination.unlink(missing_ok=True)
        if original is not None:
            atomic_write(source, original)
        raise
    return {"record": {**record, "status": status, "revision": revision(destination)}, "changed": len(changed)}


def move_record(payload, target_status):
    source = record_path(payload["slug"], payload["status"])
    target = record_path(payload["slug"], target_status)
    if not source.exists() or revision(source) != payload.get("revision"):
        raise ValueError("文章已发生变化，请刷新后重试")
    if target.exists():
        raise ValueError("目标中存在同名文章")
    snapshot(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    source.replace(target)
    try:
        changed = generate() if payload["status"] == "published" else []
    except Exception:
        target.replace(source)
        raise
    return {"changed": len(changed)}


def images():
    return [{"path": "/" + path.relative_to(ROOT).as_posix(), "name": path.name,
             "size": path.stat().st_size, "revision": revision(path)}
            for path in sorted((ROOT / "img").rglob("*"))
            if path.is_file() and path.suffix.lower() in IMAGE_TYPES and path.resolve().is_relative_to((ROOT / "img").resolve())]


def decode_image(payload, allow_ico=False):
    extension = Path(payload["name"]).suffix.lower()
    allowed = IMAGE_TYPES if allow_ico else IMAGE_TYPES - {".ico"}
    if extension not in allowed:
        raise ValueError("不支持该图片格式，请使用 PNG、JPEG、GIF、WebP" + (" 或 ICO" if allow_ico else ""))
    data = base64.b64decode(payload["data"], validate=True)
    if not data or len(data) > 12 * 1024 * 1024:
        raise ValueError("图片大小需在 1 字节至 12 MB 之间")
    detected = (".png" if data.startswith(b"\x89PNG\r\n\x1a\n") else
                ".jpg" if data.startswith(b"\xff\xd8\xff") else
                ".gif" if data.startswith((b"GIF87a", b"GIF89a")) else
                ".webp" if data.startswith(b"RIFF") and data[8:12] == b"WEBP" else
                ".ico" if data.startswith(b"\x00\x00\x01\x00") and len(data) >= 22 and int.from_bytes(data[4:6], "little") > 0 else None)
    if detected != (".jpg" if extension == ".jpeg" else extension):
        raise ValueError("文件内容与图片扩展名不符")
    return data, detected


def upload(payload, favicon=False):
    data, detected = decode_image(payload, allow_ico=favicon)
    if favicon and (detected not in (".png", ".ico") or len(data) > 2 * 1024 * 1024):
        raise ValueError("网站图标仅支持 2 MB 以内的 PNG 或 ICO")
    digest = hashlib.sha256(data).hexdigest()
    directory = ROOT / ("img/site" if favicon else "img/games/uploads")
    for existing in directory.glob("*"):
        if existing.is_file() and existing.suffix.lower().replace(".jpeg", ".jpg") == detected:
            if not existing.resolve().is_relative_to(directory.resolve()):
                continue
            if revision(existing) == digest:
                return {"path": "/" + existing.relative_to(ROOT).as_posix()}
    path = directory / (digest[:24] + detected)
    while path.exists():
        path = directory / (digest[:24] + "-" + secrets.token_hex(4) + detected)
    atomic_write(path, data)
    return {"path": "/" + path.relative_to(ROOT).as_posix()}


def replace_image(payload):
    path = image_path(payload["path"])
    current_revision = revision(path)
    if current_revision != payload.get("revision"):
        raise ValueError("图片已被其他操作修改，请刷新素材库后重新选择")
    data, detected = decode_image(payload, allow_ico=True)
    if path.suffix.lower().replace(".jpeg", ".jpg") != detected:
        raise ValueError("为保留原图片地址，请选择相同格式的图片（JPG 与 JPEG 可以互换）")
    new_revision = hashlib.sha256(data).hexdigest()
    if current_revision == new_revision:
        return {"path": payload["path"], "revision": current_revision, "changed": False}
    relative = path.relative_to(ROOT)
    backup_path = PRIVATE / "history/images" / datetime.now().strftime("%Y%m%d-%H%M%S-%f") / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    atomic_write(path, data)
    return {"path": payload["path"], "revision": new_revision, "changed": True,
            "backup": backup_path.relative_to(ROOT).as_posix()}


def backup():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in (ROOT / "content", ROOT / "img", PRIVATE / "draft", PRIVATE / "trash", PRIVATE / "history"):
            for path in directory.rglob("*"):
                if path.is_file() and path.resolve().is_relative_to(ROOT.resolve()):
                    archive.write(path, path.relative_to(ROOT).as_posix())
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *arguments):
        pass

    def respond(self, data, content_type="application/json; charset=utf-8", status=200):
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "same-origin")
        if content_type == "application/zip":
            self.send_header("Content-Disposition", 'attachment; filename="seven-blog-backup.zip"')
        self.end_headers()
        self.wfile.write(data)

    def check_host(self):
        if self.headers.get("Host") != self.server.address:
            raise ValueError("仅允许本机管理地址访问")
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.server.address:
            raise ValueError("不允许跨站请求")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise ValueError("不允许跨站请求")

    def do_GET(self):
        try:
            self.check_host()
            route = unquote(urlsplit(self.path).path)
            with LOCK:
                if route == "/api/state":
                    return self.respond({"records": list_records(), "images": images(), "token": self.server.token,
                                         "server_info": {"app": "seven-blog-studio", "api_version": 3,
                                                         "revision": BACKEND_REVISION, "workspace": WORKSPACE_ID,
                                                         "needs_restart": backend_revision() != BACKEND_REVISION}, **studio_state()})
                if route == "/api/backup":
                    return self.respond(backup(), "application/zip")
                if route in ("/manager", "/manager/"):
                    path = UI / "index.html"
                elif route.startswith("/manager/"):
                    path = (UI / route.removeprefix("/manager/")).resolve()
                    if not path.is_relative_to(UI.resolve()):
                        raise ValueError("无效路径")
                else:
                    path = (ROOT / route.lstrip("/")).resolve()
                    if not path.is_relative_to(ROOT.resolve()):
                        raise ValueError("无效路径")
                    parts = path.relative_to(ROOT).parts
                    if any(part.startswith(".") for part in parts) or (parts and parts[0] in ("content", "scripts")):
                        return self.respond({"error": "禁止访问源文件"}, status=403)
                    if path.is_dir():
                        path = path / "index.html"
                if not path.is_file():
                    return self.respond({"error": "页面不存在"}, status=404)
                return self.respond(path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        except (ValueError, OSError) as error:
            self.respond({"error": str(error)}, status=400)

    def do_POST(self):
        try:
            self.check_host()
            if backend_revision() != BACKEND_REVISION:
                return self.respond({"error": "工作台代码已更新，请关闭运行窗口并重新启动，当前操作尚未保存。"}, status=409)
            if not secrets.compare_digest(self.headers.get("X-Manager-Token", ""), self.server.token):
                return self.respond({"error": "管理会话已过期，请刷新页面"}, status=403)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 18 * 1024 * 1024:
                raise ValueError("请求大小不合法")
            payload = json.loads(self.rfile.read(length))
            with LOCK:
                if self.path == "/api/save":
                    result = save_record(payload)
                elif self.path == "/api/trash":
                    result = move_record(payload, "trash")
                elif self.path == "/api/restore":
                    if payload["status"] != "trash":
                        raise ValueError("只能恢复回收站中的文章")
                    result = move_record(payload, "draft")
                elif self.path == "/api/upload":
                    result = upload(payload)
                elif self.path == "/api/replace-image":
                    result = replace_image(payload)
                elif self.path == "/api/build":
                    result = {"changed": len(generate())}
                elif self.path == "/api/preview":
                    result = {"html": build_games.review_body(payload["record"])}
                elif self.path == "/api/projects/save":
                    result = save_document("projects", payload)
                elif self.path == "/api/about/save":
                    result = save_document("about", payload)
                elif self.path == "/api/appearance/save":
                    result = save_document("appearance", payload)
                elif self.path == "/api/site/save":
                    result = save_document("site", payload)
                elif self.path == "/api/site/icon/upload":
                    result = upload(payload, favicon=True)
                elif self.path == "/api/cloud/prepare":
                    generate()
                    result = self.server.cloud.prepare()
                elif self.path == "/api/cloud/publish":
                    result = self.server.cloud.publish(payload.get("ticket"))
                else:
                    return self.respond({"error": "接口不存在"}, status=404)
            self.respond(result)
        except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
            self.respond({"error": str(error) or "正文需要至少一段文字"}, status=400)
        except Exception:
            self.respond({"error": "操作失败，未能完成保存。请检查终端和文件权限。"}, status=500)
            raise


def main():
    parser = argparse.ArgumentParser(description="Seven 本地博客管理工具")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    arguments = parser.parse_args()
    try:
        server = ManagerServer(("127.0.0.1", arguments.port), Handler)
    except OSError as error:
        if error.errno not in (48, 98, 10013, 10048) and getattr(error, "winerror", None) not in (10013, 10048):
            raise
        try:
            with urlopen(f"http://127.0.0.1:{arguments.port}/api/state", timeout=5) as response:
                existing = json.load(response).get("server_info", {})
            if existing.get("app") == "seven-blog-studio" and existing.get("workspace") == WORKSPACE_ID and existing.get("revision") == BACKEND_REVISION and not existing.get("needs_restart"):
                address = f"http://127.0.0.1:{arguments.port}/manager/"
                print(f"Workspace already running: {address}", flush=True)
                if not arguments.no_browser:
                    webbrowser.open(address)
                return
        except (OSError, ValueError):
            pass
        raise SystemExit(f"Port {arguments.port} is occupied by an older studio or another service.\nClose the old blog manager window(s) before restarting.\nAlternatively: python scripts/blog_manager.py --port {arguments.port + 1}") from error
    server.address = f"127.0.0.1:{server.server_port}"
    server.token = secrets.token_urlsafe(32)
    server.cloud = CloudSync(ROOT)
    address = f"http://{server.address}/manager/"
    print(f"Blog manager: {address}\nLocal only. Press Ctrl+C to stop.", flush=True)
    if not arguments.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
