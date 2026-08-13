# 📈 YouTube 股票分析系統 - Antigravity 開發與運作筆記

本文檔記錄系統運作的經驗、風控注意事項與新工具的操作指南，供隨時閱讀與參考。

---

## 1. ⚠️ YouTube 字幕 API 風控與 IP 封鎖注意事項 (IP Block Warning)

- **現象與風險**：
  若短時間內頻繁呼叫 YouTube 字幕抓取 API（例如 `youtube-transcript-api` 或連續請求官方 CC 字幕），YouTube 會觸發風控驗證機制，導致 **用戶 IP 被暫時或長期封鎖 (IP Block / Rate Limit)**。
- **解決方案與最佳實踐**：
  - **純地端語音轉譯 (Faster-Whisper)**：系統已重構為直接下載影片音訊，並透過 Faster-Whisper / OpenVINO 模型進行地端轉譯，完全繞過 YouTube 官方字幕 API 的請求限制，徹底避免 IP 被封。
  - **頻率控制機制**：系統內建防封 IP 機制（單部影片之間隨機停頓 `MIN_DELAY_SECONDS` ~ `MAX_DELAY_SECONDS` 秒，以及每處理 N 部影片後分批大休眠 `BATCH_COOLDOWN_SECONDS` 秒）。

---

## 2. 🔄 `scripts/reprocess_url.py` 特定網址重跑與重新轉譯指南

- **工具用途**：
  當部分影片先前為「未能取得字幕/無CC」或研報格式需要更新時，使用本腳本精準擦除歷史舊資料，並重新進行地端 Faster-Whisper 轉譯與研報生成。

- **分批佇列機制 (`reprocess_urls.txt`)**：
  - 為防一次重跑過多影片，建議每次挑選約 10 個 URL 貼入根目錄下的 `reprocess_urls.txt` 檔案中（一行一個網址）。

- **自動連動清理流程**：
  1. **舊檔清理**：自動尋找並刪除該 URL 在 `影片筆記/` 與 `原始字幕/` 的歷史舊檔。
  2. **個股索引連動**：自動移除 `個股索引/*.md` 內的舊分析條目（若索引變成空檔則自動刪除空檔）。
  3. **歷史紀錄解鎖**：自動將該 URL 從 `processed_urls.txt` 與 `no_subtitles_urls.txt` 擦除解鎖。
  4. **重新轉譯與生成**：重新執行 Faster-Whisper 轉譯與 AI 研報生成。
  5. **佇列扣除**：成功後自動將該 URL 從 `reprocess_urls.txt` 中清除。

- **常用執行命令**：
  ```bash
  # 預設讀取 reprocess_urls.txt 中的網址（Faster-Whisper CPU 模式）
  python scripts/reprocess_url.py

  # 啟用 Intel Iris Xe 顯卡加速轉譯
  python scripts/reprocess_url.py --use-gpu

  # 限制 CPU 4 核心降頻控溫
  python scripts/reprocess_url.py --low-cpu

  # 僅預覽要刪除與清理的項目（不實際刪除/不實際執行）
  python scripts/reprocess_url.py --dry-run
  ```

---

## 3. 🛠️ 常用清理與匯出工具索引

- **`python scripts/export_failed_urls.py`**：
  掃描全庫研報，將所有「未能取得字幕/NO_CC」的影片 URL 提取並匯出至 `no_subtitles_urls.txt`。

- **`python scripts/delete_channel.py --channel "頻道名稱"`**：
  一鍵連動刪除特定頻道的所有研報筆記、原始字幕與個股索引條目。

- **`python scripts/clean_urls.py`**：
  比對 `urls.txt` 與 `processed_urls.txt`，刪除 `urls.txt` 中已處理過的重複網址。

- **`python web/app.py`**：
  啟動內網跨裝置研報閱讀器 (Web Reader)，服務綁定 `0.0.0.0`（預設 Port `23300`，如被保留可用 `--port` 自訂），同 Wi-Fi 內網的所有手機、平板與電腦皆可隨時開啟閱讀。

- **`python scripts/fetch_daily_new_videos.py`**：
  每日自動巡檢 `subscribed_channels.txt` 內 7 個訂閱頻道的最新影片，過濾已處理過的歷史紀錄，將新影片合併追加至 `urls.txt`。（包含 Windows 排程任務 `YouTubeStockAnalyzerDaily2AM` 於每日凌晨 02:00 自動執行）


