import html
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit


DEFAULT = {"name": "Seven", "tagline": "", "avatar": "", "body": "", "links": []}


def read_about(root):
    path = root / "content/about.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(DEFAULT)


def validate_about(record, root):
    if not isinstance(record, dict):
        raise ValueError("关于资料必须是对象")
    for field in ("name", "tagline", "avatar", "body"):
        if not isinstance(record.get(field), str):
            raise ValueError("关于资料缺少字段：" + field)
    if not record["name"].strip() or len(record["name"]) > 100 or len(record["body"]) > 100000:
        raise ValueError("请填写姓名（不超过 100 字），正文不超过 10 万字")
    if record["avatar"]:
        value = record["avatar"]
        path = (root / value.lstrip("/")).resolve()
        if not value.startswith("/img/") or not path.is_relative_to((root / "img").resolve()) or not path.is_file():
            raise ValueError("头像必须选择 /img/ 下的本地图片")
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"):
            raise ValueError("头像格式不支持")
    if not isinstance(record.get("links"), list) or len(record["links"]) > 20:
        raise ValueError("最多添加 20 个个人链接")
    for link in record["links"]:
        if not isinstance(link, dict) or not isinstance(link.get("label"), str) or not link["label"].strip() or not isinstance(link.get("url"), str):
            raise ValueError("链接需填写名称和 HTTPS 地址")
        parsed = urlsplit(link["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or any(character.isspace() for character in link["url"]):
            raise ValueError("个人链接必须是无账号密码的 HTTPS 地址")


def add_about(outputs, root, replace_main):
    if not (root / "content/about.json").exists():
        return
    record = read_about(root)
    validate_about(record, root)
    avatar = f'<img class="about-avatar" src="{html.escape(record["avatar"], quote=True)}" alt="{html.escape(record["name"])}">' if record["avatar"] else ""
    blocks = []
    for line in record["body"].splitlines():
        if not line.strip():
            continue
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(line.strip()))
        tag = "h2" if text.startswith("## ") else "p"
        blocks.append(f'<{tag}>{text[3:] if tag == "h2" else text}</{tag}>')
    links = "".join(f'<a class="about-link" href="{html.escape(link["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(link["label"])} ↗</a>' for link in record["links"])
    content = f'<div id="page"><div class="container managed-about" id="article-container">{avatar}<h1>{html.escape(record["name"])}</h1><p class="about-tagline">{html.escape(record["tagline"])}</p>{"".join(blocks)}<div class="about-links">{links}</div></div></div>'
    document = replace_main(outputs.get("about/index.html", (root / "about/index.html").read_text(encoding="utf-8")), content)
    stylesheet = '<link rel="stylesheet" href="/css/about.css">'
    if stylesheet not in document:
        document = document.replace("</head>", stylesheet + "\n</head>")
    outputs["about/index.html"] = document
    search = ET.fromstring(outputs["search.xml"])
    for entry in list(search):
        if entry.findtext("url") == "/about/":
            search.remove(entry)
    entry = ET.SubElement(search, "entry")
    ET.SubElement(entry, "title").text = "关于 " + record["name"]
    ET.SubElement(entry, "link", {"href": "/about/"})
    ET.SubElement(entry, "url").text = "/about/"
    ET.SubElement(entry, "content", {"type": "html"}).text = html.escape(record["tagline"] + "\n" + record["body"])
    ET.indent(search, space="  ")
    outputs["search.xml"] = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(search, encoding="unicode") + "\n"
