# 📈 YouTube 股票分析 AI 自動化筆記工具 (YouTube Stock Analyzer)

一個基於 Gemini AI 與 Python 的自動化工具。專為股票與投資類 YouTube 影片設計，自動抓取字幕與頻道資訊，依頻道自動歸類生成 Markdown 投資筆記，並連動即時股價 (yfinance) 與個股歷史觀點交叉索引。

---

## 🌟 核心功能 (Features)

- 📁 **頻道自動分層**：生成的筆記自動儲存於 `影片筆記/<頻道名稱>/<日期>_<標題>.md`。
- 🎙️ **雙重逐字稿備援**：優先讀取 CC 字幕；無字幕時自動透過 Gemini Audio 模態轉譯。
- 📊 **即時股價對照**：識別台股 (`2330.TW`) 與美股 (`NVDA`) 標的，調用 `yfinance` 獲取最新股價、漲跌幅與 P/E。
- 📌 **個股交叉索引連動**：自動維護 `個股索引/<股票代號>.md`，記錄所有提及該股票的歷史影片與時間軸。
- 📝 **逐字稿自動備份**：原始字幕備份至 `原始字幕/<頻道名稱>/`。

---

## 📂 目錄架構 (Directory Structure)

```text
.
├── 影片筆記/                    # 依頻道名稱分類存放筆記 MD (Ignored in Git)
├── 個股索引/                    # 個股歷史觀點彙總索引 (Ignored in Git)
├── 原始字幕/                    # 原始逐字稿 txt 備份 (Ignored in Git)
├── scripts/
│   ├── main.py                  # CLI 主程式
│   ├── yt_extractor.py          # yt-dlp 元資料與字幕/音訊處理
│   ├── summarizer.py            # Gemini AI 結構化總結與標的提取
│   ├── stock_market.py          # yfinance 即時股價數據
│   ├── stock_indexer.py         # 個股索引檔連動更新器
│   └── config.py                # 系統設定與路徑
├── .env.example                 # API Key 設定範本
├── .gitignore
└── requirements.txt
```

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝套件
```bash
pip install -r requirements.txt
```

### 2. 設定 API Key
複製 `.env.example` 為 `.env` 並填入您的 Gemini API Key：
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 執行指令
```bash
# 處理單一影片
python scripts/main.py --url "https://www.youtube.com/watch?v=XXXXXX"

# 批次處理文字檔內的 URL 清單
python scripts/main.py --file urls.txt

# 互動模式
python scripts/main.py
```
