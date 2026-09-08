import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://seven39c5bb.github.io"
MAIN_START = '<main class="layout" id="content-inner">'
ASIDE_START = '<div class="aside-content"'
MENU = '<div class="menus_item"><a class="site-page" href="/games/"><i class="fa-fw fas fa-gamepad"></i><span> 游戏评测</span></a></div>'


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def replace_main(document, content):
    start = document.index(MAIN_START) + len(MAIN_START)
    end = document.index(ASIDE_START, start)
    return document[:start] + content + document[end:]


def inline(text):
    escaped = html.escape(re.sub(r"\\([\\^*_~])", r"\1", text))
    escaped = re.sub(r"~~(.+?)~~", r"<del>\1</del>", escaped)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def paragraphs(record):
    return [line.strip() for line in record["body"].splitlines()
            if line.strip() and line.strip() != "<empty-block/>"]


def excerpt(record):
    return next(line for line in paragraphs(record)
                if not line.startswith("![") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", line))[:140]


def score(record):
    match = re.search(r"(?:游戏|个人)?评分[：:]\s*(\d+(?:\.\d+)?)", record["body"])
    if not match:
        raise ValueError(f'Missing rating: {record["slug"]}')
    return match.group(1)


def review_body(record):
    blocks = []
    for line in paragraphs(record):
        image = re.fullmatch(r"!\[([^\]]*)\]\((/img/games/[^)]+)\)", line)
        if image:
            caption, image_path = image.groups()
            if not (ROOT / image_path.lstrip("/")).is_file():
                raise ValueError(f"Missing image: {image_path}")
            caption_html = f"<figcaption>{inline(caption.strip())}</figcaption>" if caption.strip() else ""
            alternate = caption.strip() or record["title"] + " 游戏截图"
            blocks.append(f'<figure><img src="{html.escape(image_path)}" alt="{html.escape(alternate)}" loading="lazy" decoding="async">{caption_html}</figure>')
        else:
            blocks.append(f"<p>{inline(line)}</p>")
    return "\n".join(blocks)


def shared(document, post_count, tag_count, category_count):
    if 'href="/games/"' not in document.split(MAIN_START)[0]:
        document = document.replace('<div class="menus_items">', '<div class="menus_items">' + MENU)
    for route, count in [("archives", post_count), ("tags", tag_count), ("categories", category_count)]:
        pattern = rf'(<a href="/{route}/"><div class="headline">.*?</div><div class="length-num">)\d+(</div></a>)'
        document = re.sub(pattern, lambda match: match[1] + str(count) + match[2], document)
    return document


def make_page(template, title, route, content, description, record=None):
    document = replace_main(template, content)
    escaped_title = html.escape(title)
    document = re.sub(r"<title>.*?</title>", f"<title>{escaped_title} | Seven39c5bb</title>", document)
    document = re.sub(r'<h1 id="site-title">.*?</h1>', f'<h1 id="site-title">{escaped_title}</h1>', document)
    document = re.sub(r"  title: '[^']*',", "  title: " + json.dumps(title, ensure_ascii=False) + ",", document)
    document = re.sub(r'<meta (?:name|property)="(?:description|og:[^"]+|article:[^"]+|twitter:[^"]+)"[^>]*>', "", document)
    document = re.sub(r'<link rel="canonical"[^>]*>', "", document)
    metadata = [
        f'<link rel="canonical" href="{SITE_URL}{route}">',
        f'<meta name="description" content="{html.escape(description, quote=True)}">',
        f'<meta property="og:title" content="{escaped_title}">',
        f'<meta property="og:type" content="{"article" if record else "website"}">',
        f'<meta property="og:url" content="{SITE_URL}{route}">',
        '<meta property="og:site_name" content="Seven39c5bb">',
        f'<meta property="og:description" content="{html.escape(description, quote=True)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<link rel="stylesheet" href="/css/games.css">',
    ]
    if record:
        metadata += [f'<meta property="og:image" content="{SITE_URL}{record["cover"]}">',
                     f'<meta property="article:published_time" content="{record["imported"]}T00:00:00+08:00">']
    document = document.replace("</head>", "\n" + "\n".join(metadata) + "\n</head>")
    return "\n".join(line.rstrip() for line in document.splitlines()) + "\n"


def game_card(record):
    route = f'/games/{record["slug"]}/'
    return f'''<article class="game-card">
<a class="game-card-cover" href="{route}" aria-label="{html.escape(record["title"])}"><img src="{record["cover"]}" alt="{html.escape(record["title"])}" loading="lazy" decoding="async"></a>
<div class="game-card-copy"><span class="game-score">个人评分 {score(record)}</span>
<h2><a href="{route}">{html.escape(record["title"])}</a></h2>
<p>{html.escape(excerpt(record))}…</p>
<span class="game-date">原文更新于 <time datetime="{record["source_updated"]}">{record["source_updated"][:10]}</time></span>
</div></article>'''


def home_card(record):
    route = f'/games/{record["slug"]}/'
    return f'''<div class="recent-post-item game-home-card" data-game-review="{record["slug"]}">
<div class="post_cover left"><a href="{route}" aria-label="{html.escape(record["title"])}"><img class="post-bg" src="{record["cover"]}" alt="{html.escape(record["title"])}" loading="lazy" decoding="async"></a></div>
<div class="recent-post-info"><a class="article-title" href="{route}" title="{html.escape(record["title"])}">{html.escape(record["title"])}</a>
<div class="article-meta-wrap"><a href="/categories/games/">游戏评测</a> · 个人评分 {score(record)} · 迁移于 <time datetime="{record["imported"]}">{record["imported"]}</time></div>
<div class="content">{html.escape(excerpt(record))}…</div></div></div>'''


def archive_item(title, route, date, label="发表于"):
    return f'''<div class="article-sort-item no-article-cover"><div class="article-sort-item-info"><div class="article-sort-item-time"><i class="far fa-calendar-alt"></i><time datetime="{date}" title="{label} {date}">{date}</time><span> · {label}</span></div><a class="article-sort-item-title" href="{route}" title="{html.escape(title)}">{html.escape(title)}</a></div></div>'''


def archive_content(title, items):
    return f'<div id="archive"><div class="article-sort-title">{html.escape(title)}</div><div class="article-sort">{items}</div></div>'


def build():
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "content/games").glob("*.json"))]
    records.sort(key=lambda record: record["source_updated"], reverse=True)
    if not records:
        raise ValueError("No game reviews found")
    template = read("about/index.html")
    outputs = {}
    for record in records:
        original_date = record["body"].splitlines()[0]
        original_note = f'原文日期：{original_date} · ' if re.fullmatch(r"\d{4}-\d{2}-\d{2}", original_date) else ""
        content = f'''<div id="page" class="game-review"><article>
<div class="game-review-meta"><a href="/games/">游戏评测</a><span class="game-score">个人评分 {score(record)}</span></div>
<div class="game-import-note">{original_note}Notion 原文更新：<time datetime="{record["source_updated"]}">{record["source_updated"][:10]}</time> · 迁移至博客：<time datetime="{record["imported"]}">{record["imported"]}</time><br>保留原文观点与评分，文中的时间表述以原文写作时为准。可能包含剧透。</div>
<div class="container game-review-body" id="article-container">
{review_body(record)}
</div><nav class="game-back"><a href="/games/">← 返回全部游戏评测</a></nav></article></div>'''
        route = f'/games/{record["slug"]}/'
        outputs[route.lstrip("/") + "index.html"] = make_page(template, record["title"], route, content, excerpt(record), record)

    gallery = f'''<div id="page" class="games-index"><div class="game-intro"><p>我的游玩记录、主观感受与评分。</p><p>共 {len(records)} 篇评测，从 Notion 整理迁入，保留原文及配图。</p></div><div class="game-grid">{"".join(game_card(record) for record in records)}</div></div>'''
    outputs["games/index.html"] = make_page(template, "游戏评测", "/games/", gallery, "Seven 的游戏评测：游玩记录、主观感受与评分。")

    home = read("index.html")
    home = re.sub(r'<!-- game-reviews:start -->.*?<!-- game-reviews:end -->', "", home, flags=re.S)
    cards = '<!-- game-reviews:start -->\n' + "\n".join(home_card(record) for record in records) + '\n<!-- game-reviews:end -->'
    home = home.replace('<div class="recent-post-items">', '<div class="recent-post-items">' + cards, 1)
    home = home.replace('class="recent-posts nc"', 'class="recent-posts"')
    outputs["index.html"] = home

    entries = "".join(archive_item(record["title"], f'/games/{record["slug"]}/', record["imported"], "迁移于") for record in records)
    for route, title in [("categories/games", "分类 - 游戏评测"), ("tags/games", "标签 - 游戏评测")]:
        outputs[f"{route}/index.html"] = make_page(template, title, f"/{route}/", archive_content(f"{title} - {len(records)}", entries), title)

    tags = read("tags/index.html")
    if 'href="/tags/games/"' not in tags:
        tags = tags.replace('<div class="tag-cloud-list text-center">', '<div class="tag-cloud-list text-center"><a href="/tags/games/" style="font-size: 1.5em;">游戏评测</a>')
    outputs["tags/index.html"] = tags
    categories = read("categories/index.html")
    category_link = f'<li class="category-list-item" data-game-category="true"><a class="category-list-link" href="/categories/games/">游戏评测</a><span class="category-list-count">{len(records)}</span></li>'
    categories = re.sub(r'<li class="category-list-item" data-game-category="true">.*?</li>', "", categories, flags=re.S)
    if '<ul class="category-list">' in categories:
        categories = categories.replace('<ul class="category-list">', '<ul class="category-list">' + category_link, 1)
    else:
        categories = categories.replace('<div class="container" id="article-container">', '<div class="container" id="article-container"><ul class="category-list">' + category_link + '</ul>', 1)
    outputs["categories/index.html"] = categories

    archive = read("archives/index.html")
    archive = re.sub(r'<!-- game-archives:start -->.*?<!-- game-archives:end -->', "", archive, flags=re.S)
    groups = {}
    for record in records:
        groups.setdefault(record["imported"][:4], []).append(record)
    migrated = "".join(f'<div class="article-sort-item year">{year}</div>' + "".join(archive_item(record["title"], f'/games/{record["slug"]}/', record["imported"], "迁移于") for record in group) for year, group in sorted(groups.items(), reverse=True))
    archive = archive.replace('<div class="article-sort">', '<div class="article-sort"><!-- game-archives:start -->' + migrated + '<!-- game-archives:end -->', 1)
    old_count = len(re.findall(r'<a class="article-sort-item-title"', re.sub(r'<!-- game-archives:start -->.*?<!-- game-archives:end -->', "", archive, flags=re.S)))
    post_count = old_count + len(records)
    archive = re.sub(r'全部文章 - \d+', f'全部文章 - {post_count}', archive)
    outputs["archives/index.html"] = archive
    for year, group in groups.items():
        for period in [year] + sorted({record["imported"][:7].replace("-", "/") for record in group}):
            selected = [record for record in group if record["imported"].replace("-", "/").startswith(period)]
            items = "".join(archive_item(record["title"], f'/games/{record["slug"]}/', record["imported"], "迁移于") for record in selected)
            route = f"/archives/{period}/"
            title = period.replace("/", "年 ") + ("月" if "/" in period else "年")
            outputs[route.lstrip("/") + "index.html"] = make_page(template, title, route, archive_content(f"迁移文章 - {len(selected)}", items), title + "游戏评测归档")

    search = ET.fromstring(read("search.xml"))
    for entry in list(search):
        if (entry.findtext("url") or "").startswith("/games/"):
            search.remove(entry)
    for record in reversed(records):
        entry = ET.Element("entry")
        ET.SubElement(entry, "title").text = record["title"]
        route = f'/games/{record["slug"]}/'
        ET.SubElement(entry, "link", {"href": route})
        ET.SubElement(entry, "url").text = route
        ET.SubElement(entry, "content", {"type": "html"}).text = review_body(record)
        ET.SubElement(ET.SubElement(entry, "tags"), "tag").text = "游戏评测"
        search.insert(0, entry)
    ET.indent(search, space="  ")
    outputs["search.xml"] = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(search, encoding="unicode") + "\n"
    tag_count = len(re.findall(r'href="/tags/[^/]+/"', outputs["tags/index.html"].split('<div class="tag-cloud-list text-center">')[1].split('</div>')[0]))
    category_count = len(re.findall(r'class="category-list-link"', outputs["categories/index.html"]))
    for path in ROOT.rglob("*.html"):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in outputs:
            outputs[relative] = path.read_text(encoding="utf-8")
    for path, document in list(outputs.items()):
        if path.endswith(".html"):
            outputs[path] = shared(document, post_count, tag_count, category_count)
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build static game reviews and blog indexes from local Notion snapshots.")
    parser.add_argument("--check", action="store_true", help="Verify committed output matches the content snapshots.")
    arguments = parser.parse_args()
    stale = []
    for filename, content in build().items():
        destination = ROOT / filename
        if destination.exists() and destination.read_text(encoding="utf-8") == content:
            continue
        stale.append(filename)
        if not arguments.check:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
    if arguments.check and stale:
        raise SystemExit("Out-of-date pages: " + ", ".join(stale))
    print("All game-review pages are up to date." if arguments.check else f"Updated {len(stale)} files.")
