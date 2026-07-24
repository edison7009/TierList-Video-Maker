# TierList Video Maker（视频榜单制作器）

一个 Claude Code / Codex 技能，把任意**已发布**的 [TierVibe](https://tiervibe.com) 榜单做成带讲解的视频。

## 它做什么

- **抓取**榜单数据 + 卡片图（TierVibe 公开读取 API）
- **从公开页面截取高清整图**（Playwright 跑和页面里「下载整图」按钮同一套 `html-to-image` 导出——自动化、不走 TierVibe 服务器）
- **AI 视觉**识别每张卡片（API 不返回文字标签）
- **讲解稿**——生成后先给你审，确认再生产
- **TTS** 用 edge-tts（多语言、跨平台）
- **视频**——层级区滚动背景 + 卡片放大叠层 + 字幕（SRT）

> **仅限已发布帖子。** 这个技能把**已发布**的 TierVibe 榜单做成视频。草稿 / 还在编辑器里编辑中的帖子没有整图、也不公开可读，做不成视频——请先在 TierVibe 上发布。

## 为什么整图来自浏览器截图

TierVibe 服务器只存榜单的 600px 缩略图，没有高清版。要 1080p 清晰背景，这个技能在脚本里复刻「下载整图」这个用户本地动作：无头 Chromium 打开**公开**读帖页，对层级区 DOM 跑 `html-to-image`。整图导出始终是客户端行为——**为整图请求不触碰 TierVibe 服务器**——脚本只是替人点了那个按钮。

> 需要 TierVibe 已部署读帖页上的 `data-testid="tier-grid"` 属性。若截图步骤报「tier-grid not found」，技能会退回 600px 服务器缩略图。

## 快速开始

1. 安装技能(见下),然后说：*「帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx」*
2. 审一下生成的讲解稿
3. 拿到视频 + `.srt`

## 仓库结构（双 marketplace）

这个仓库内置**两份** marketplace 目录,让同一插件既能装进 Claude Code,又能装进 Codex/ChatGPT 类工具：

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

把这个仓库加为 marketplace,再装插件：

```
/plugin marketplace add edison7009/TierList-Video-Maker
/plugin install tierlist-video-maker@tiervibe-com
```

触发词如「把这个 TierVibe 做成视频」自动加载,或用 `/tiervibe-com:tierlist-video-maker` 调用。

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
| `scripts/tts_narration.py` | 从讲解稿生成 TTS 音频 |
| `scripts/generate_video.py` | 合成视频：滚动背景 + 字幕 |

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

TierVibe logo 放在 `plugins/tierlist-video-maker/assets/logo.svg`（沿用 TierList-Maker 插件同一品牌），Codex 的 `.codex-plugin/plugin.json` 用 `interface.logo` 指向它。marketplace 列表 UI 的图标,可在 GitHub/GitCode 仓库的社交预览图设成同一张 logo。

## 许可

MIT
