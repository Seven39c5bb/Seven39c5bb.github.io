import hashlib
import html
import json
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit


DEFAULT = {"favicon": "/img/favicon.ico", "links": []}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def validate(record, root):
    if not isinstance(record, dict) or set(record) != {"favicon", "links"}:
        raise ValueError("网站设置字段不完整，请刷新工作台后重试")
    favicon = record["favicon"]
    if not isinstance(favicon, str):
        raise ValueError("网站图标路径必须是文本")
    if favicon:
        path = (root / favicon.lstrip("/")).resolve()
        if not favicon.startswith("/img/") or not path.is_relative_to((root / "img").resolve()) or not path.is_file():
            raise ValueError("网站图标必须选择 /img/ 下已存在的本地图片")
        if path.suffix.lower() not in (".png", ".ico"):
            raise ValueError("网站图标仅支持 PNG 或 ICO")
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("网站图标不能超过 2 MB")
        valid = data.startswith(b"\x89PNG\r\n\x1a\n") if path.suffix.lower() == ".png" else data.startswith(b"\x00\x00\x01\x00") and len(data) >= 22 and int.from_bytes(data[4:6], "little") > 0
        if not valid:
            raise ValueError("网站图标内容与扩展名不符")
    if not isinstance(record["links"], list) or len(record["links"]) > 20:
        raise ValueError("最多添加 20 个个人主页链接")
    links = []
    for link in record["links"]:
        if not isinstance(link, dict) or set(link) != {"label", "url", "enabled"}:
            raise ValueError("个人主页链接需包含名称、地址和启用状态")
        if not isinstance(link["label"], str) or not 1 <= len(link["label"].strip()) <= 40:
            raise ValueError("链接名称需为 1–40 个字符")
        if type(link["enabled"]) is not bool:
            raise ValueError("链接启用状态必须是布尔值")
        url = link["url"]
        if not isinstance(url, str) or not 1 <= len(url) <= 2048 or any(character.isspace() or ord(character) < 32 for character in url) or "\\" in url:
            raise ValueError("请输入有效的 HTTPS 个人主页地址")
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("个人主页地址端口无效") from error
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or port == 0:
            raise ValueError("个人主页地址必须是无账号密码的 HTTPS 链接")
        links.append({"label": link["label"].strip(), "url": url, "enabled": link["enabled"]})
    return {"favicon": favicon, "links": links}


def read_site(root):
    path = root / "content/site.json"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {**DEFAULT, "links": []}
    return validate(record, root)


def profile_links(record):
    links = "".join(f'<a href="{html.escape(link["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(link["label"])}<span aria-hidden="true"> ↗</span></a>' for link in record["links"] if link["enabled"])
    return f'<nav class="managed-profile-links" aria-label="个人主页">{links}</nav>' if links else ""


class SiteMarkup(HTMLParser):
    def __init__(self, document, links, favicon):
        super().__init__(convert_charrefs=False)
        self.document = document
        self.links = links
        self.favicon = favicon
        self.frames = []
        self.edits = []
        self.offsets = [0]
        for line in document.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))

    def source_offset(self):
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        classes = set((attrs.get("class") or "").split())
        start = self.source_offset()
        if tag == "link" and "icon" in (attrs.get("rel") or "").lower().split():
            self.edits.append((start, start + len(self.get_starttag_text()), ""))
        if tag in VOID_TAGS:
            return
        remove = bool(classes & {"site-data", "card-info-social-icons", "managed-profile-links"}) or attrs.get("id") == "site_social_icons"
        insert = attrs.get("id") in {"site-info", "sidebar-menus"} or {"card-widget", "card-info"}.issubset(classes)
        self.frames.append((tag, start, remove, insert))

    def handle_startendtag(self, tag, attributes):
        self.handle_starttag(tag, attributes)
        if tag not in VOID_TAGS:
            self.frames.pop()

    def handle_endtag(self, tag):
        start = self.source_offset()
        if tag == "head":
            self.edits.append((start, start, self.favicon))
        for position in range(len(self.frames) - 1, -1, -1):
            frame_tag, frame_start, remove, insert = self.frames[position]
            if frame_tag != tag:
                continue
            del self.frames[position:]
            if remove:
                end = self.document.index(">", start) + 1
                self.edits.append((frame_start, end, ""))
            elif insert and self.links:
                self.edits.append((start, start, self.links))
            break

    def render(self):
        self.feed(self.document)
        self.close()
        removals = [(start, end) for start, end, text in self.edits if end > start]
        edits = [(start, end, text) for start, end, text in self.edits
                 if not any(outer_start <= start < outer_end and end <= outer_end and (outer_start, outer_end) != (start, end)
                            for outer_start, outer_end in removals)]
        document = self.document
        for start, end, text in sorted(edits, reverse=True):
            document = document[:start] + text + document[end:]
        return document


def style_document(document, record, root):
    favicon = ""
    if record["favicon"]:
        path = root / record["favicon"].lstrip("/")
        version = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        mime = "image/png" if path.suffix.lower() == ".png" else "image/x-icon"
        url = quote(record["favicon"], safe="/")
        favicon = f'<link rel="icon" type="{mime}" href="{url}?v={version}">'
    return SiteMarkup(document, profile_links(record), favicon).render()


def add_site(outputs, root):
    record = read_site(root)
    for name, document in list(outputs.items()):
        if name.endswith(".html"):
            outputs[name] = style_document(document, record, root)
