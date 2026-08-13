import argparse
import sys
import io
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
CHANNELS_FILE = BASE_DIR / "subscribed_channels.txt"
URLS_FILE = BASE_DIR / "urls.txt"
PROCESSED_URLS_FILE = BASE_DIR / "processed_urls.txt"

def load_processed_urls() -> set:
    """載入已處理過的 URL 歷史紀錄"""
    if PROCESSED_URLS_FILE.exists():
        lines = [l.strip() for l in PROCESSED_URLS_FILE.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip()]
        return set(lines)
    return set()

def load_subscribed_channels() -> list:
    """載入訂閱的 YouTube 頻道清單"""
    if CHANNELS_FILE.exists():
        lines = [l.strip() for l in CHANNELS_FILE.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip() and not l.startswith('#')]
        return lines
    return []

def fetch_recent_videos_for_channel(channel_url: str, days_limit: int = 2) -> list:
    """
    透過 yt-dlp 扁平化爬取頻道最新發布的影片資訊 (不下載影音內容)
    """
    new_video_urls = []
    
    # 確保網址為 Videos 分頁
    clean_url = channel_url.rstrip('/')
    if not clean_url.endswith('/videos'):
        fetch_target = f"{clean_url}/videos"
    else:
        fetch_target = clean_url

    cmd = [
        'yt-dlp',
        '--flat-playlist',
        '--playlist-end', '5',
        '-J',
        fetch_target
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=30)
        if res.returncode != 0:
            print(f"⚠️ 無法讀取頻道 {channel_url}: {res.stderr[:100]}")
            return []

        data = json.loads(res.stdout)
        channel_name = data.get('title') or data.get('uploader') or channel_url
        entries = data.get('entries', [])
        
        # 以現在時間往前推算 N 天 (預設過去 48 小時內發布)
        cutoff_date = datetime.now() - timedelta(days=days_limit)
        
        for entry in entries:
            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
            title = entry.get('title', '未知標題')
            
            # yt-dlp 的 timestamp 可能是以 epoch 或 YYYYMMDD 提供
            timestamp = entry.get('timestamp')
            upload_date_str = entry.get('upload_date')
            
            is_recent = False
            if timestamp:
                pub_date = datetime.fromtimestamp(timestamp)
                if pub_date >= cutoff_date:
                    is_recent = True
            elif upload_date_str and len(upload_date_str) == 8:
                try:
                    pub_date = datetime.strptime(upload_date_str, "%Y%m%d")
                    if pub_date >= cutoff_date:
                        is_recent = True
                except ValueError:
                    is_recent = True
            else:
                # 預設保護：包含最新前 2 部
                is_recent = True

            if is_recent and video_url not in new_video_urls:
                new_video_urls.append((video_url, title, channel_name))

    except Exception as e:
        print(f"❌ 爬取頻道 {channel_url} 失敗: {e}")

    return new_video_urls

def load_existing_urls() -> list:
    """載入 urls.txt 目前已有的網址清單"""
    if URLS_FILE.exists():
        lines = [l.strip() for l in URLS_FILE.read_text(encoding='utf-8', errors='ignore').splitlines() if l.strip()]
        return lines
    return []

def main():
    parser = argparse.ArgumentParser(description="每日自動巡檢 YouTube 頻道最新影片並寫入 urls.txt 腳本")
    parser.add_argument("--auto-process", action="store_true", help="抓完 URL 後自動執行 main.py --low-cpu 轉換研報")
    parser.add_argument("--days", type=int, default=2, help="只抓取最近 N 天內發布的最新影片 (預設 2 天)")
    args = parser.parse_args()

    print("=" * 65)
    print("🔍 啟動每日 YouTube 頻道最新影片自動巡檢作業...")
    print(f"🕒 當前系統時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    channels = load_subscribed_channels()
    if not channels:
        print("⚠️ 未發現任何訂閱頻道！請檢查 subscribed_channels.txt 檔案。")
        return

    processed_urls = load_processed_urls()
    existing_urls = load_existing_urls()
    print(f"📋 共加載 {len(channels)} 個訂閱頻道，歷史紀錄 {len(processed_urls)} 筆，目前 urls.txt 已有 {len(existing_urls)} 筆。")

    all_new_urls = []
    
    for idx, ch_url in enumerate(channels, 1):
        print(f"\n[{idx}/{len(channels)}] 正在巡檢頻道: {ch_url} ...")
        recent_videos = fetch_recent_videos_for_channel(ch_url, days_limit=args.days)
        
        for video_url, title, channel_name in recent_videos:
            if video_url in processed_urls:
                print(f"  - [已處理跳過] {title}")
            elif video_url in existing_urls or video_url in all_new_urls:
                print(f"  - [已在佇列中] {title}")
            else:
                print(f"  - 🌟 [發現最新影片] {title}")
                all_new_urls.append(video_url)

        
        time.sleep(1)

    print("\n" + "=" * 65)
    
    # 合併現有 urls.txt 與新網址 (去重並保持順序)
    combined_urls = []
    for u in existing_urls + all_new_urls:
        if u not in combined_urls:
            combined_urls.append(u)

    if all_new_urls:
        print(f"🎉 本次巡檢新增 {len(all_new_urls)} 個最新發布的影片 URL！(urls.txt 總計 {len(combined_urls)} 筆)")
        URLS_FILE.write_text("\n".join(combined_urls) + "\n", encoding='utf-8')
        print(f"📄 已成功合併寫入: {URLS_FILE.name}")
    else:
        print(f"✨ 巡檢完畢：所有頻道今日均無新上架影片。保留 urls.txt 原有內容 ({len(combined_urls)} 筆)。")

    # 若指定了 --auto-process 且 urls.txt 有待處理網址，自動啟動 low CPU 程序
    if args.auto_process and combined_urls:
        print("\n🚀 正在自動啟動主程序 (main.py --file urls.txt --low-cpu) 進行研報轉換...")
        cmd = [sys.executable, str(SCRIPTS_DIR / "main.py"), "--file", str(URLS_FILE), "--low-cpu"]
        subprocess.run(cmd, cwd=str(BASE_DIR))

if __name__ == "__main__":
    main()

