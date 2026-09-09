import hashlib
import json
import re


DEFAULT = {
    "transition_color": "#39c5bb",
    "primary_color": "#49b1f5",
    "hover_color": "#ff7242",
    "light_background": "#ffffff",
    "dark_background": "#0d0d0d",
    "light_card": "#ffffff",
    "dark_card": "#121212",
    "card_radius": 8,
    "font_size": 14,
    "header_height": 400,
    "transition_duration": 500,
}
LIMITS = {"card_radius": (0, 32), "font_size": (12, 22),
          "header_height": (200, 600), "transition_duration": (0, 2000)}


def validate(record):
    if not isinstance(record, dict) or set(record) != set(DEFAULT):
        raise ValueError("样式配置字段不完整，请刷新工作台后重试")
    for name in DEFAULT:
        value = record[name]
        if name in LIMITS:
            minimum, maximum = LIMITS[name]
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} 必须是 {minimum}–{maximum} 之间的整数")
        elif not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("颜色请使用六位 HEX 格式，例如 #39c5bb：" + name)
    return {name: value.lower() if isinstance(value, str) else value for name, value in record.items()}


def read_appearance(root):
    path = root / "content/appearance.json"
    return validate(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else dict(DEFAULT)


def stylesheet(record):
    values = validate(record)
    primary = values["primary_color"]
    red, green, blue = (int(primary[offset:offset + 2], 16) for offset in (1, 3, 5))
    return f''':root, [data-theme="light"], [data-theme="dark"] {{
  --site-transition-color: {values["transition_color"]};
  --site-primary-color: {primary};
  --site-hover-color: {values["hover_color"]};
  --btn-bg: {primary};
  --btn-hover-color: {values["hover_color"]};
  --pseudo-hover: {values["hover_color"]};
  --scrollbar-color: {primary};
  --default-bg-color: {primary};
  --preloader-bg: {values["transition_color"]};
  --text-bg-hover: rgba({red}, {green}, {blue}, 0.7);
  --blockquote-bg: rgba({red}, {green}, {blue}, 0.1);
  --hr-border: {primary};
  --hr-before-color: {primary};
}}
:root, [data-theme="light"] {{
  --global-bg: {values["light_background"]};
  --card-bg: {values["light_card"]};
}}
[data-theme="dark"] {{
  --global-bg: {values["dark_background"]};
  --card-bg: {values["dark_card"]};
}}
body {{ font-size: {values["font_size"]}px; }}
#page-header {{
  transition-duration: {values["transition_duration"]}ms;
}}
#page-header:not(.not-top-img)::after {{
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-color: var(--site-transition-color);
  opacity: 0;
  animation: site-header-tint {values["transition_duration"]}ms ease-out;
}}
@keyframes site-header-tint {{
  from {{ opacity: 0.85; }}
  to {{ opacity: 0; }}
}}
#page-header.not-home-page:not(.not-top-img) {{ height: {values["header_height"]}px; }}
#aside-content .card-widget, #recent-posts > .recent-post-item,
.layout > #page, .layout > #post, .layout > #archive,
.project-card {{ border-radius: {values["card_radius"]}px; }}
#article-container a, .game-review-meta a, .game-back a {{ color: var(--site-primary-color); }}
#article-container a:hover, #recent-posts > .recent-post-item > .recent-post-info > .article-title:hover {{ color: var(--site-hover-color); }}
.project-button {{ background: var(--site-primary-color); }}
.project-button:hover {{ background: var(--site-hover-color); }}
@media (prefers-reduced-motion: reduce) {{
  #page-header {{ transition-duration: 0ms; }}
  #page-header::after {{ animation: none; }}
}}
'''


def style_document(document, version):
    document = re.sub(r'<link\b[^>]*href="/css/appearance\.css(?:\?[^"]*)?"[^>]*>\s*', "", document)
    document = document.replace('href="/css/custom.css" media="defer" onload="this.media=\'all\'"', 'href="/css/custom.css"')
    return document.replace("</head>", f'<link rel="stylesheet" href="/css/appearance.css?v={version}">\n</head>', 1)


def add_appearance(outputs, root):
    css = stylesheet(read_appearance(root))
    version = hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
    for name, document in list(outputs.items()):
        if name.endswith(".html"):
            outputs[name] = style_document(document, version)
    outputs["css/appearance.css"] = css
