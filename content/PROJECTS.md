# 游戏作品展示

「游戏作品」展示自己制作的游戏，与 `content/games/` 中的游戏评测分开。页面地址为 `/projects/`，首页和全站导航都有入口。

编辑 `content/projects.json`，数组中的每个对象对应一张作品卡片，显示顺序与数组顺序一致。目前已收录《失光 · Fiat Less》。如果数组为空，网站会显示「作品资料正在整理中」，不展示虚构项目。

## 添加作品

以下仅为字段格式示例，请替换成真实作品信息后再加入数组：

```json
[
  {
    "slug": "my-first-game",
    "title": "你的游戏名称",
    "description": "介绍游戏玩法、特色，以及你在这个项目中做了什么。",
    "status": "开发中",
    "engine": "Unity",
    "role": "独立开发",
    "tags": ["解谜", "2D"]
  }
]
```

必填字段为 `slug`、`title`、`description`。`slug` 使用小写字母、数字、单连字符，不能重复，它也是作品的页面锚点，如 `/projects/#my-first-game`。

可选字段：

| 字段 | 用途 |
| --- | --- |
| `status` | 开发中、可试玩、已发布等真实状态 |
| `engine` | 使用的引擎 |
| `role` | 你承担的职责 |
| `tags` | 类型、平台等标签，字符串数组 |
| `cover` | 封面图片地址，建议 16:9；留空使用图标封面 |
| `steam_url` | Steam 商店页面，显示「在 Steam 查看」，不表示已经发售或可直接试玩 |
| `play_url` | 可直接游玩的浏览器试玩页面，显示「开始游玩」 |
| `download_url` | 游戏下载地址，显示「下载游戏」 |
| `source_url` | 代码仓库地址，显示「查看源码」 |

链接支持 HTTPS 或站内绝对路径。站内路径对应的文件或目录必须存在，例如将截图放入 `img/projects/` 后填写 `/img/projects/cover.jpg`。不填写链接时不会出现对应按钮，也不会生成无效占位按钮。外部链接在新标签页打开。

《失光》的封面、中文名称、玩法简介和发行状态依据其 [Steam 商店页面](https://store.steampowered.com/app/4614120/Fiat_Less/) 整理。封面保存在 `img/projects/fiat-less/header.jpg`，按 Steam 横幅比例完整显示。发行状态是手动维护的快照，不会自动与 Steam 同步；发售后请更新 `status` 并重新生成。开发引擎和个人职责尚未填写，待作者确认后补充。

## 生成与检查

在仓库根目录运行：

```powershell
python scripts/build_games.py
python scripts/build_games.py --check
```

游戏评测工作台的重新生成流程也会保留并更新此分区，但工作台暂不提供作品表单，作品资料请直接编辑 JSON。游戏作品不计入评测文章数；作品标题和简介会加入站内搜索索引。

这是静态展示分区，不自动打包游戏。要提供网页试玩，需要先部署游戏，再填写链接。审核生成文件后自行提交并推送，才会更新线上网站。
