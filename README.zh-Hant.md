# TierList Video Maker（影片榜單製作器）

> English: [README.md](README.md) ｜ 简体：[README.zh-CN.md](README.zh-CN.md)

> 一個堪比「印鈔機」的產生影片 skill —— 一鍵全自動把 TierVibe 榜單做成帶講解的影片，而且每個環節都比同類產生器更硬核。

## 快速展示

**1. 製作帖子。** 給 AI 工具安裝 **TierList-Maker** 後，在 AI 工具中輸入：

```
/tierlist-maker 幫我製作一個美國最受歡迎體育TierList，要有詳細解說。
```

成果：
- 中文版：<https://tiervibe.com/t/ZY70IpV0K8>
- 英文版：<https://tiervibe.com/t/UxDgrOcQxd>

---

**2. 生成影片。** 給 AI 工具安裝 **TierList-Video-Maker** 後，在 AI 工具中輸入：

```
/tierlist-video-maker 把 https://tiervibe.com/t/ZY70IpV0K8 製作成影片
```

（英文版：把 <https://tiervibe.com/t/UxDgrOcQxd> 製作成影片）

影片展示：
- 中文版（B 站）：<https://www.bilibili.com/video/BV1LG3F6sEAB>
- 英文版（YouTube）：<https://youtu.be/ANjyhxRrH9U>

## 為什麼 TierList 影片值得做

TierList 類型的影片自帶**深度與話題性**——誰排第幾、誰被拉黑、誰該進 S 級，天然就是爭議和談資。這類內容在幾乎所有影片平台都**很容易爆**，幫你拿到大量播放，進而帶粉、帶貨、帶流量。

## 為什麼比其他「AI 產生影片」那類更強？

市面上已經有影片產生器，但做出來的影片普遍**很一般**：縮圖放大糊掉、卡片認錯位、開頭結尾靜音、字幕和語音對不上、整張圖從頭擺到尾沒有節奏。這個 skill 把每一步都做扎實了：

- **Board-first AI 視覺識別** —— AI 先看**整張看板**（有 tier 標籤 + 鄰卡上下文）識別所有卡片，再逐張高解析度圖對照確認，看板是 tier / 順序的真相源。不是孤立認一張張小 logo → 認得準、不錯位。
- **真·高畫質整圖背景** —— Playwright 截公開頁 `[data-testid="tier-grid"]`，~2560px 寬，不是把 600px 縮圖撐大糊掉。
- **AI 寫講解稿，先給你審再產生** —— 不是死板模板朗讀；想改就改，確認了才合成。
- **多語言自然人聲 TTS** —— 中 / 英 / 日 / 韓，edge-tts 跨平台，開場白 + 結尾都有配音（不是開頭結尾靜音）。
- **字幕時軸跟真實音訊走** —— SRT 按每段音訊實測時長產生，不是固定 3 秒猜，字幕和語音對得上。
- **卡片放大疊層 + 層級區滾動背景** —— 講到哪張卡它就置中放大，背景跟著滾到對應位置，視覺有節奏，不是死板整圖從頭放到尾。
- **配 `TierList-Maker`** —— 先做有深度、有內容的榜，再做影片，內容質量從源頭就贏。

## 兩步法，就這麼簡單

1. 先用 **[TierList-Maker](https://github.com/edison7009/TierList-Maker)** 做一張有深度、有內容的榜單，發布到 [tiervibe.com](https://tiervibe.com)。
2. 複製已發布榜單的連結（`https://tiervibe.com/t/xxxxx`）丟給本 skill —— 它全自動把榜單做成帶講解的影片。

> **僅限已發布貼文。** 草稿 / 還在編輯器裡編輯中的貼文沒有整圖、也不公開可讀，做不成影片——請先在 TierVibe 上發布。

## 它做什麼

- **抓取**榜單資料 + 卡片圖（TierVibe 公開讀取 API）
- **從公開頁面擷取高畫質整圖**（Playwright 跑和頁面裡「下載整圖」按鈕同一套 `html-to-image` 匯出——自動化、不走 TierVibe 伺服器）
- **AI 視覺**識別每張卡片（board-first：先整圖、再逐張對照，看板為準）
- **講解稿**——產生後先給你審，確認再產生
- **TTS** 用 edge-tts（多語言、跨平台，含開場白 / 結尾配音）
- **影片**——層級區滾動背景 + 卡片放大疊層 + 字幕（SRT 時軸跟音訊）

## 快速開始

1. 安裝技能（見下），然後說：*「幫我把這個 TierVibe 做成影片: https://tiervibe.com/t/xxxxx」*
2. 審一下產生的講解稿
3. 拿到影片 + `.srt`

## 為什麼整圖來自瀏覽器截圖

TierVibe 伺服器只存榜單的 600px 縮圖，沒有高畫質版。要 1080p 清晰背景，這個技能在腳本裡復刻「下載整圖」這個使用者本地動作：無頭 Chromium 開啟**公開**讀帖頁，對層級區 DOM 跑 `html-to-image`。整圖匯出始終是用戶端行為——**為整圖請求不觸碰 TierVibe 伺服器**——腳本只是替人點了那個按鈕。

> 需要 TierVibe 已部署讀帖頁上的 `data-testid="tier-grid"` 屬性。若截圖步驟報「tier-grid not found」，技能會退回 600px 伺服器縮圖。

## 倉庫結構（雙 marketplace）

這個倉庫內建**兩份** marketplace 目錄，讓同一外掛既能裝進 Claude Code，又能裝進 Codex/ChatGPT 類工具：

```
TierList-Video-Maker/
├── .claude-plugin/
│   └── marketplace.json            # Claude Code marketplace 目錄
├── .agents/plugins/
│   └── marketplace.json            # Codex / ChatGPT 類 marketplace 目錄
├── plugins/
│   └── tierlist-video-maker/
│       ├── .claude-plugin/plugin.json   # Claude Code 外掛清單
│       ├── .codex-plugin/plugin.json     # Codex 外掛清單（帶 logo）
│       └── skills/tierlist-video-maker/{SKILL.md, references/, scripts/}
└── README.md
```

## 安裝 — Claude Code

把這個倉庫加為 marketplace，再裝外掛：

```
/plugin marketplace add edison7009/TierList-Video-Maker
/plugin install tierlist-video-maker@video-maker
```

觸發詞如「把這個 TierVibe 做成影片」自動載入，或用 `/video-maker:tierlist-video-maker` 呼叫。

## 安裝 — ChatGPT

1. 開啟 ChatGPT → **Plugins**。
2. 點右上角 **⬇️** 圖示。
3. 選 **Add plugin marketplace**。
4. 貼上倉庫 URL：`https://github.com/edison7009/TierList-Video-Maker.git`
5. 確認；`tierlist-video-maker` 出現在外掛列表裡 —— 啟用它。

然後在對話裡說 *「幫我把這個 TierVibe 做成影片: https://tiervibe.com/t/xxxxx」* 觸發。AI 抓板+卡片圖、擷取高畫質整圖、產生講解稿給你審、再算繪影片。

## 安裝 — Codex (CLI)

倉庫內建 `.agents/plugins/marketplace.json`（Codex schema）。新增並啟用：

```
codex plugin marketplace add edison7009/TierList-Video-Maker
```

## 腳本

| 腳本 | 作用 |
|---|---|
| `scripts/fetch_tierlist.py` | 抓榜單資料 + 下卡片圖 + 伺服器縮圖 |
| `scripts/capture_board.py` | 從公開頁擷取高畫質整圖（Playwright） |
| `scripts/render_board.py` | 兜底：用卡片圖重拼一張近似整圖 |
| `scripts/reconcile_cards.py` | Board-first：整圖識別結果與逐張對照，看板為準重排 |
| `scripts/tts_narration.py` | 從講解稿產生 TTS 音訊（含開場 / 結尾） |
| `scripts/build_card_manifest.py` | 產生人讀的對照表（檔案 ↔ 名稱 ↔ tier ↔ 講解） |
| `scripts/generate_video.py` | 合成影片：滾動背景 + 卡片疊層 + 字幕 |

## 相依套件

- Python 3.10+
- `Pillow`
- `edge-tts`（自動安裝）
- `moviepy>=2.0` + `numpy`（自動安裝；自帶 ffmpeg）
- `playwright` + Chromium（首次跑 `capture_board.py` 時自動安裝；約 150MB 瀏覽器）

## 跨平台

- Windows：Microsoft YaHei (msyh.ttc)
- macOS：PingFang SC
- Linux：Noto Sans CJK

## 圖示

TierVibe logo 放在 `plugins/tierlist-video-maker/assets/logo.svg`（沿用 TierList-Maker 外掛同一品牌），Codex 的 `.codex-plugin/plugin.json` 用 `interface.logo` 指向它。marketplace 列表 UI 的圖示，可在 GitHub/GitCode 倉庫的社群預覽圖設成同一張 logo。

## 授權

MIT
