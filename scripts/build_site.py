import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit


DEFAULT = {"favicon": "/img/site/pixel-mint.svg", "links": []}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
NAV_TOOLS = '''<div id="nav-tools" role="group" aria-label="阅读工具">
<button type="button" data-tool="translateLink" aria-label="简繁转换"><span id="translateLink" aria-hidden="true">简</span></button>
<button type="button" id="darkmode" aria-label="切换明暗"><svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor"/></svg></button>
<button type="button" id="hide-aside-btn" aria-label="单栏或双栏"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8h16m-4-4 4 4-4 4M20 16H4m4-4-4 4 4 4"/></svg></button>
<button type="button" id="go-up" aria-label="回到顶部"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20V4m-6 6 6-6 6 6"/></svg></button>
</div>'''


def validate_svg(data):
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError("SVG 图标不能超过 2 MB")
    try:
        text = data.decode("utf-8-sig")
        text = re.sub(r"^\s*<\?xml\s[^?]*\?>", "", text, count=1)
        if "<!" in text or "<?" in text:
            raise ValueError("SVG 图标不能包含实体、DOCTYPE、外部样式表或其他声明")
        document = ET.fromstring(text)
    except (UnicodeError, ET.ParseError) as error:
        raise ValueError("请输入有效的 UTF-8 SVG 文件") from error
    namespace = "{http://www.w3.org/2000/svg}"
    if document.tag != namespace + "svg":
        raise ValueError("SVG 图标缺少标准 SVG 根元素")
    allowed = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "title", "desc"}
    numeric = {"x", "y", "width", "height", "rx", "ry", "cx", "cy", "r", "x1", "x2", "y1", "y2", "stroke-width"}
    for element in document.iter():
        if not element.tag.startswith(namespace) or element.tag[len(namespace):] not in allowed:
            raise ValueError("SVG 仅支持静态几何图形，不能包含脚本、外链、图片或动画")
        for name, value in element.attrib.items():
            if name in ("fill", "stroke"):
                valid = value == "none" or bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value))
            elif name in numeric:
                valid = bool(re.fullmatch(r"-?\d+(?:\.\d+)?", value))
            elif name in ("viewBox", "points"):
                valid = bool(re.fullmatch(r"[-\d.,\s]+", value))
            elif name == "d":
                valid = bool(re.fullmatch(r"[MmZzLlHhVvCcSsQqTtAaEe\d\s.,+\-]+", value))
            elif name == "shape-rendering":
                valid = value in ("auto", "crispEdges", "geometricPrecision")
            elif name == "fill-rule":
                valid = value in ("nonzero", "evenodd")
            elif name == "role":
                valid = value == "img"
            elif name == "aria-label":
                valid = len(value) <= 200
            else:
                valid = False
            if not valid:
                raise ValueError("SVG 包含不支持或不安全的属性：" + name)
    viewbox = document.get("viewBox", "").replace(",", " ").split()
    if len(viewbox) != 4 or not all(re.fullmatch(r"-?\d+(?:\.\d+)?", part) for part in viewbox) or float(viewbox[2]) <= 0 or float(viewbox[3]) <= 0:
        raise ValueError("SVG 需要有效的 viewBox 和正数宽高")


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
        if path.suffix.lower() not in (".png", ".ico", ".svg"):
            raise ValueError("网站图标仅支持 PNG、ICO 或安全的静态 SVG")
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("网站图标不能超过 2 MB")
        if path.suffix.lower() == ".svg":
            validate_svg(data)
            valid = True
        else:
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
        remove = bool(classes & {"site-data", "card-info-social-icons", "managed-profile-links"}) or attrs.get("id") in {"site_social_icons", "rightside", "nav-tools"}
        insert = self.links if attrs.get("id") in {"site-info", "sidebar-menus"} or {"card-widget", "card-info"}.issubset(classes) else ""
        if attrs.get("id") == "blog-info":
            insert = NAV_TOOLS
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
            elif insert:
                position = self.document.index(">", start) + 1 if insert == NAV_TOOLS else start
                self.edits.append((position, position, insert))
            break

    def render(self):
        self.feed(self.document)
        self.close()
        removals = [(start, end) for start, end, text in self.edits if end > start]
        edits = [(start, end, text) for start, end, text in self.edits
                 if not any(outer_start <= start < outer_end and end <= outer_end and (outer_start, outer_end) != (start, end)
                            and not (start == end == outer_start)
                            for outer_start, outer_end in removals)]
        document = self.document
        for start, end, text in sorted(edits, reverse=True):
            document = document[:start] + text + document[end:]
        return document


def style_document(document, record, root):
    favicon = ""
    if record["favicon"]:
        path = root / record["favicon"].lstrip("/")
        data = path.read_bytes()
        if path.suffix.lower() == ".svg":
            data = data.replace(b"\r\n", b"\n")
        version = hashlib.sha256(data).hexdigest()[:12]
        mime = {".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml"}[path.suffix.lower()]
        url = quote(record["favicon"], safe="/")
        favicon = f'<link rel="icon" type="{mime}" href="{url}?v={version}">'
    return SiteMarkup(document, profile_links(record), favicon).render()


def add_site(outputs, root):
    record = read_site(root)
    for name, document in list(outputs.items()):
        if name.endswith(".html"):
            outputs[name] = style_document(document, record, root)
