import html
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit


ROUTE = "/projects/"
TITLE = "游戏作品"
DESCRIPTION = "从一个想法，到一个可以游玩的世界。这里收录我制作的游戏、原型与实验。"
MENU = '<div class="menus_item"><a class="site-page" href="/projects/"><i class="fa-fw fas fa-code"></i><span> 游戏作品</span></a></div>'
STYLE = '<link rel="stylesheet" href="/css/projects.css">'


def safe_url(value, root, field):
    if not value or any(character.isspace() for character in value) or "\\" in value:
        raise ValueError(f"Invalid project {field}: {value!r}")
    parsed = urlsplit(value)
    if value.startswith("/") and not value.startswith("//"):
        destination = (root / unquote(parsed.path).lstrip("/")).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.exists():
            raise ValueError(f"Missing or invalid local project {field}: {value}")
    elif parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Project {field} must be a local path or HTTPS URL: {value}")
    return html.escape(value, quote=True)


def load_projects(root):
    records = json.loads((root / "content/projects.json").read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("content/projects.json must contain an array")
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each project must be an object")
        for field in ("slug", "title", "description"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"Missing project {field}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", record["slug"]) or record["slug"] in seen:
            raise ValueError(f'Invalid or duplicate project slug: {record["slug"]}')
        seen.add(record["slug"])
        for field in ("status", "engine", "role", "cover", "steam_url", "play_url", "download_url", "source_url"):
            if field in record and not isinstance(record[field], str):
                raise ValueError(f"Project {field} must be a string")
        tags = record.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ValueError("Project tags must be an array of nonempty strings")
    return records


def project_card(record, root):
    title = html.escape(record["title"])
    cover = '<div class="project-cover project-cover-placeholder" aria-hidden="true"><i class="fas fa-gamepad"></i></div>'
    if record.get("cover"):
        cover_class = "project-cover project-cover-steam" if record.get("steam_url") else "project-cover"
        cover = f'<div class="{cover_class}"><img src="{safe_url(record["cover"], root, "cover")}" alt="{title} 游戏封面" loading="lazy" decoding="async"></div>'
    status = f'<span class="project-status">{html.escape(record["status"])}</span>' if record.get("status") else ""
    tags = "".join(f'<span>{html.escape(tag)}</span>' for tag in record.get("tags", []))
    details = "".join(f'<div><dt>{label}</dt><dd>{html.escape(record[field])}</dd></div>'
                      for field, label in [("engine", "开发引擎"), ("role", "我的职责")] if record.get(field))
    actions = []
    for field, label in [("steam_url", "在 Steam 查看"), ("play_url", "开始游玩"), ("download_url", "下载游戏"), ("source_url", "查看源码")]:
        if record.get(field):
            address = safe_url(record[field], root, field)
            external = ' target="_blank" rel="noopener noreferrer"' if record[field].startswith("https://") else ""
            actions.append(f'<a class="project-button" href="{address}"{external}>{label}<span class="project-sr-only">：{title}</span><span aria-hidden="true"> ↗</span></a>')
    return f'''<article class="project-card" id="{record['slug']}">
{cover}<div class="project-copy">{status}<h3>{title}</h3>
<p>{html.escape(record['description'])}</p><div class="project-tags">{tags}</div>
<dl class="project-details">{details}</dl><div class="project-actions">{"".join(actions)}</div></div></article>'''


def add_projects(outputs, root, template, make_page):
    records = load_projects(root)
    cards = "".join(project_card(record, root) for record in records)
    empty = '''<div class="projects-empty"><span class="projects-empty-icon" aria-hidden="true"><i class="fas fa-gamepad"></i></span>
<h3>下一次冒险，从这里开始</h3><p>作品资料正在整理中，之后会在这里分享游戏画面、开发故事与游玩入口。</p>
<a class="project-text-link" href="/games/">先看看我的游戏评测 <span aria-hidden="true">→</span></a></div>'''
    content = f'''<div id="page" class="projects-index">
<section class="projects-collection" aria-labelledby="collection-heading"><div class="projects-section-heading"><h2 id="collection-heading">我的作品</h2><span>MY GAMES</span></div>
{f'<div class="projects-grid">{cards}</div>' if records else empty}</section></div>'''
    outputs["projects/index.html"] = make_page(template, TITLE, ROUTE, content, DESCRIPTION)
    for path, document in list(outputs.items()):
        if not path.endswith(".html"):
            continue
        document = document.replace(MENU, "")
        document = document.replace('<div class="menus_items">', '<div class="menus_items">' + MENU)
        if path == "projects/index.html" and STYLE not in document:
            document = document.replace("</head>", STYLE + "\n</head>")
        outputs[path] = document
    search = ET.fromstring(outputs["search.xml"])
    for entry in list(search):
        if (entry.findtext("url") or "").startswith(ROUTE):
            search.remove(entry)
    for title, address, description in [(TITLE, ROUTE, DESCRIPTION)] + [
            (record["title"], ROUTE + "#" + record["slug"], record["description"]) for record in records]:
        entry = ET.SubElement(search, "entry")
        ET.SubElement(entry, "title").text = title
        ET.SubElement(entry, "link", {"href": address})
        ET.SubElement(entry, "url").text = address
        ET.SubElement(entry, "content", {"type": "html"}).text = html.escape(description)
        ET.SubElement(ET.SubElement(entry, "tags"), "tag").text = TITLE
    ET.indent(search, space="  ")
    outputs["search.xml"] = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(search, encoding="unicode") + "\n"
