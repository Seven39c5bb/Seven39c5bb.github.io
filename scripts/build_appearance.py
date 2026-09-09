import hashlib
import json
import re
from pathlib import Path


DEFAULT = {
    "transition_color": "#39c5bb",
    "primary_color": "#387f79",
    "hover_color": "#2c6863",
    "light_background": "#f2f5f1",
    "dark_background": "#182522",
    "light_card": "#fcfdf9",
    "dark_card": "#22332f",
    "card_radius": 16,
    "font_size": 15,
    "header_height": 400,
    "transition_duration": 350,
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
  --site-brand-color: {values["transition_color"]};
  --site-configured-primary: {primary};
  --site-configured-hover: {values["hover_color"]};
  --site-card-radius: {values["card_radius"]}px;
  --global-font-size: {values["font_size"]}px;
  --site-primary-color: {primary};
  --site-hover-color: {values["hover_color"]};
  --btn-bg: {primary};
  --btn-hover-color: {values["hover_color"]};
  --pseudo-hover: {values["hover_color"]};
  --scrollbar-color: {primary};
  --default-bg-color: {primary};
  --preloader-bg: {values["transition_color"]};
  --text-bg-hover: {primary};
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
  from {{ opacity: 0.24; }}
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
''' + (Path(__file__).resolve().parent.parent / "css/palette.css").read_text(encoding="utf-8")


def style_document(document, version):
    document = re.sub(r'<link\b[^>]*href="/css/appearance\.css(?:\?[^"]*)?"[^>]*>\s*', "", document)
    document = document.replace('href="/css/custom.css" media="defer" onload="this.media=\'all\'"', 'href="/css/custom.css"')
    inline_colors = {"#ddd": "var(--site-border-color)", "#eee": "var(--site-soft-bg)",
                     "#999": "var(--site-muted-color)", "$theme-color": "var(--site-primary-color)"}
    def theme_inline_style(match):
        return re.sub(r"#(?:ddd|eee|999)\b|\$theme-color", lambda color: inline_colors[color.group()], match.group())
    document = re.sub(r'\bstyle="[^"]*"', theme_inline_style, document)
    document = re.sub(r'(<script\b[^>]*id="canvas_nest"[^>]*\bcolor=")[^"]*', r'\g<1>107,153,145', document)
    document = re.sub(r'(<script\b[^>]*id="canvas_nest"[^>]*\bopacity=")[^"]*', r'\g<1>0.25', document)
    return document.replace("</head>", f'<link rel="stylesheet" href="/css/appearance.css?v={version}">\n</head>', 1)


def add_appearance(outputs, root):
    css = stylesheet(read_appearance(root))
    version = hashlib.sha256(css.encode("utf-8")).hexdigest()[:12]
    for name, document in list(outputs.items()):
        if name.endswith(".html"):
            outputs[name] = style_document(document, version)
    outputs["css/appearance.css"] = css
