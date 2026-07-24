# TierList Video Maker（视频榜单制作器）

一个 Claude Code / Codex 技能，把任意**已发布**的 [TierVibe](https://tiervibe.com) 榜单做成带讲解的视频。

## 它做什么

- **抓取**榜单数据 + 卡片图（TierVibe 公开读取 API）
- **从公开页面截取高清整图**（Playwright 跑和页面里「下载整图」按钮同一套 `html-to-image` 导出——自动化、不走 TierVibe 服务器）
- **AI 视觉**识别每张卡片（API 不返回文字标签）
- **讲解稿**——生成后先给你审，确认再生产
- **TTS** 用 edge-tts（多语言、跨平台）
- **视频**——层级区滚动背景 + 卡片放大叠层 + 字幕（SRT）

## 为什么整图来自浏览器截图

TierVibe 服务器只存榜单的 600px 缩略图，没有高清版。要 1080p 清晰背景，这个技能在脚本里复刻「下载整图」这个用户本地动作：无头 Chromium 打开**公开**读帖页，对层级区 DOM 跑 `html-to-image`。整图导出始终是客户端行为——**为整图请求不触碰 TierVibe 服务器**——脚本只是替人点了那个按钮。

> 需要 TierVibe 已部署读帖页上的 `data-testid="tier-grid"` 属性。若截图步骤报「tier-grid not found」，技能会退回 600px 服务器缩略图。

## 快速开始

1. 作为技能安装（拷到 `~/.claude/skills/` 或 `~/.codex/skills/tierlist-video-maker/`）。
2. 说：*「帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx」*
3. 审一下生成的讲解稿
4. 拿到视频 + `.srt`

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
- `Pillow`、`requests`
- `edge-tts`（自动安装）
- `moviepy>=2.0` + `numpy`（自动安装；自带 ffmpeg）
- `playwright` + Chromium（首次跑 `capture_board.py` 时自动安装；约 150MB 浏览器）

## 跨平台

- Windows：Microsoft YaHei (msyh.ttc)
- macOS：PingFang SC
- Linux：Noto Sans CJK

## 许可

MIT
