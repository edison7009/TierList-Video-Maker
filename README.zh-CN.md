# TierList Video Maker（视频榜单制作器）

> 一个堪比「印钞机」的生成视频 skill —— 一键全自动把 TierVibe 榜单做成带讲解的视频，而且每个环节都比同类生成器更硬核。

## 为什么 TierList 视频值得做

TierList 类型的视频自带**深度和话题度**——谁排第几、谁被拉黑、谁该进 S 级，天然就是争议和谈资。这类内容在几乎所有视频平台都**很容易爆**，帮你拿到大量播放，进而带粉、带货、带流量。

## 为什么比「印钞机」那类更强

市面上已经有「印钞机」式的 TierList 视频生成器，但做出来的视频普遍**很一般**：缩略图放大糊掉、卡片认错位、开头结尾静音、字幕和语音对不上、整张图从头摆到尾没有节奏。这个 skill 把每一步都做扎实了：

- **Board-first AI 视觉识别** —— AI 先看**整张看板**（有 tier 标签 + 邻卡上下文）识别所有卡片，再逐张高分辨率图对照确认，看板是 tier / 顺序的真相源。不是孤立认一张张小 logo → 认得准、不错位。
- **真·高清整图背景** —— Playwright 截公开页 `[data-testid="tier-grid"]`，~2560px 宽，不是把 600px 缩略图撑大糊掉。
- **AI 写讲解稿，先给你审再生产** —— 不是死板模板朗读；想改就改，确认了才合成。
- **多语言自然人声 TTS** —— 中 / 英 / 日 / 韩，edge-tts 跨平台，开场白 + 结尾都有配音（不是开头结尾静音）。
- **字幕时轴跟真实音频走** —— SRT 按每段音频实测时长生成，不是固定 3 秒猜，字幕和语音对得上。
- **卡片放大叠层 + 层级区滚动背景** —— 讲到哪张卡它就居中放大，背景跟着滚到对应位置，视觉有节奏，不是死板整图从头放到尾。
- **配 `TierList-Maker`** —— 先做有深度、有内容的榜，再做视频，内容质量从源头就赢。

## 两步法，就这么简单

1. 先用 **[TierList-Maker](https://github.com/edison7009/TierList-Maker)** 做一张有深度、有内容的榜单，发布到 [tiervibe.com](https://tiervibe.com)。
2. 复制已发布榜单的链接（`https://tiervibe.com/t/xxxxx`）丢给本 skill —— 它全自动把榜单做成带讲解的视频。

> **仅限已发布帖子。** 草稿 / 还在编辑器里编辑中的帖子没有整图、也不公开可读，做不成视频——请先在 TierVibe 上发布。

## 它做什么

- **抓取**榜单数据 + 卡片图（TierVibe 公开读取 API）
- **从公开页面截取高清整图**（Playwright 跑和页面里「下载整图」按钮同一套 `html-to-image` 导出——自动化、不走 TierVibe 服务器）
- **AI 视觉**识别每张卡片（board-first：先整图、再逐张对照，看板为准）
- **讲解稿**——生成后先给你审，确认再生产
- **TTS** 用 edge-tts（多语言、跨平台，含开场白 / 结尾配音）
- **视频**——层级区滚动背景 + 卡片放大叠层 + 字幕（SRT 时轴跟音频）

## 快速开始

1. 安装技能（见下），然后说：*「帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx」*
2. 审一下生成的讲解稿
3. 拿到视频 + `.srt`

## 为什么整图来自浏览器截图

TierVibe 服务器只存榜单的 600px 缩略图，没有高清版。要 1080p 清晰背景，这个技能在脚本里复刻「下载整图」这个用户本地动作：无头 Chromium 打开**公开**读帖页，对层级区 DOM 跑 `html-to-image`。整图导出始终是客户端行为——**为整图请求不触碰 TierVibe 服务器**——脚本只是替人点了那个按钮。

> 需要 TierVibe 已部署读帖页上的 `data-testid="tier-grid"` 属性。若截图步骤报「tier-grid not found」，技能会退回 600px 服务器缩略图。

## 仓库结构（双 marketplace）

这个仓库内置**两份** marketplace 目录，让同一插件既能装进 Claude Code，又能装进 Codex/ChatGPT 类工具：

```
TierList-Video-Maker/
├── .claude-plugin/
│   └── marketplace.json            # Claude Code marketplace 目录
├── .agents/plugins/
│   └── marketplace.json            # Codex / ChatGPT 类 marketplace 目录
├── plugins/
│   └── tierlist-video-maker/
│       ├── .claude-plugin/plugin.json   # Claude Code 插件清单
│       ├── .codex-plugin/plugin.json     # Codex 插件清单（带 logo）
│       └── skills/tierlist-video-maker/{SKILL.md, references/, scripts/}
└── README.md
```

## 安装 — Claude Code

把这个仓库加为 marketplace，再装插件：

```
/plugin marketplace add edison7009/TierList-Video-Maker
/plugin install tierlist-video-maker@video-maker
```

触发词如「把这个 TierVibe 做成视频」自动加载，或用 `/video-maker:tierlist-video-maker` 调用。

## 安装 — ChatGPT

1. 打开 ChatGPT → **Plugins**。
2. 点右上角 **⬇️** 图标。
3. 选 **Add plugin marketplace**。
4. 粘贴仓库 URL：`https://github.com/edison7009/TierList-Video-Maker.git`
5. 确认；`tierlist-video-maker` 出现在插件列表里 —— 启用它。

然后在对话里说 *「帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx」* 触发。AI 抓板+卡片图、截高清整图、生成讲解稿给你审、再渲染视频。

## 安装 — Codex (CLI)

仓库内置 `.agents/plugins/marketplace.json`（Codex schema）。添加并启用：

```
codex plugin marketplace add edison7009/TierList-Video-Maker
```

## 脚本

| 脚本 | 作用 |
|---|---|
| `scripts/fetch_tierlist.py` | 抓榜单数据 + 下卡片图 + 服务器缩略图 |
| `scripts/capture_board.py` | 从公开页截取高清整图（Playwright） |
| `scripts/render_board.py` | 兜底：用卡片图重拼一张近似整图 |
| `scripts/reconcile_cards.py` | Board-first：整图识别结果与逐张对照，看板为准重排 |
| `scripts/tts_narration.py` | 从讲解稿生成 TTS 音频（含开场 / 结尾） |
| `scripts/build_card_manifest.py` | 生成人读的对照表（文件 ↔ 名称 ↔ tier ↔ 讲解） |
| `scripts/generate_video.py` | 合成视频：滚动背景 + 卡片叠层 + 字幕 |

## 依赖

- Python 3.10+
- `Pillow`
- `edge-tts`（自动安装）
- `moviepy>=2.0` + `numpy`（自动安装；自带 ffmpeg）
- `playwright` + Chromium（首次跑 `capture_board.py` 时自动安装；约 150MB 浏览器）

## 跨平台

- Windows：Microsoft YaHei (msyh.ttc)
- macOS：PingFang SC
- Linux：Noto Sans CJK

## 图标

TierVibe logo 放在 `plugins/tierlist-video-maker/assets/logo.svg`（沿用 TierList-Maker 插件同一品牌），Codex 的 `.codex-plugin/plugin.json` 用 `interface.logo` 指向它。marketplace 列表 UI 的图标，可在 GitHub/GitCode 仓库的社交预览图设成同一张 logo。

## 许可

MIT
