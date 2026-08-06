import argparse
import sys
import io
import time
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8 編碼以防止 cp950 編碼錯誤
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 將 scripts 目錄加入 python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

import random
from config import (
    GEMINI_API_KEY, 
    BASE_DIR, 
    NO_SUBTITLES_FILE, 
    PROCESSED_URLS_FILE,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    BATCH_SIZE,
    BATCH_COOLDOWN_SECONDS
)
from yt_extractor import get_video_info, extract_video_id, get_transcript, save_transcript
from summarizer import generate_summary, save_note
from stock_indexer import update_stock_index
from logger import logger

console = Console(force_terminal=True)

def append_url_to_file(file_path: Path, url: str):
    """追加 URL 至指定 txt 檔案 (自動去重)"""
    existing_urls = []
    if file_path.exists():
        existing_urls = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        
    if url not in existing_urls:
        existing_urls.append(url)
        file_path.write_text("\n".join(existing_urls), encoding="utf-8")

def remove_url_from_file(file_path: Path, url: str):
    """自 txt 檔案移除指定的 URL"""
    if file_path.exists():
        existing_urls = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if url in existing_urls:
            existing_urls.remove(url)
            file_path.write_text("\n".join(existing_urls), encoding="utf-8")

def get_processed_urls() -> set:
    """獲取已處理完成的 URL 集合"""
    if PROCESSED_URLS_FILE.exists():
        return set([l.strip() for l in PROCESSED_URLS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()])
    return set()

def process_youtube_url(url: str, allow_audio_fallback: bool = False, index: int = 1, total: int = 1, threads: int = None) -> str:
    """
    處理單一 YouTube URL
    回傳處理結果: "SUCCESS", "SKIP_NO_CC", "ALREADY_PROCESSED", "ERROR"
    """
    console.print(f"\n[bold cyan]🚀 [{index}/{total}] 開始處理 YouTube 影片:[/bold cyan] {url}")
    logger.log(f"[{index}/{total}] 開始處理網址: {url}")
    
    video_id = extract_video_id(url)
    if not video_id:
        msg = f"[{index}/{total}] [ERROR] 無法解析影片 ID: {url}"
        console.print(f"[bold red]❌ {msg}[/bold red]")
        logger.log(msg, level="ERROR")
        return "ERROR"

    # 1. 抓取影片元資料
    with console.status("[bold green]正在抓取影片資訊 (標題, 頻道, 日期)...[/bold green]"):
        try:
            info = get_video_info(url)
            console.print(f"  [bold gold1]頻道:[/bold gold1] {info['channel']}")
            console.print(f"  [bold gold1]標題:[/bold gold1] {info['title']}")
            console.print(f"  [bold gold1]日期:[/bold gold1] {info['upload_date']}")
        except Exception as e:
            msg = f"[{index}/{total}] [ERROR] 抓取資訊失敗: {e}"
            console.print(f"[bold red]❌ {msg}[/bold red]")
            logger.log(msg, level="ERROR")
            return "ERROR"

    # 2. 檢查與抓取字幕
    with console.status("[bold green]正在檢查字幕狀態...[/bold green]"):
        transcript_data = get_transcript(video_id, url, allow_audio_fallback=allow_audio_fallback, threads=threads)

        
    # 若不允許音訊轉譯且無 CC 字幕 ➔ 暫存 URL 至 no_subtitles_urls.txt 並跳過
    if not transcript_data['has_cc'] and not allow_audio_fallback:
        append_url_to_file(NO_SUBTITLES_FILE, url)
        msg = f"[{index}/{total}] [SKIP_NO_CC] 標題: '{info['title']}' -> 無預設 CC 字幕，已暫存至 no_subtitles_urls.txt (API 0次)"
        console.print(f"  [bold yellow]ℹ️ {msg}[/bold yellow]")
        logger.log(msg, level="INFO")
        return "SKIP_NO_CC"

    transcript_text = transcript_data['text']
    transcript_source = transcript_data['source']
    console.print(f"  [dim]字幕來源: {transcript_source}[/dim]")
        
    # 保存原始字幕 txt
    transcript_path = save_transcript(info['channel'], info['upload_date'], info['title'], transcript_text)
    console.print(f"  [dim]📄 逐字稿已備份至: {transcript_path.relative_to(BASE_DIR)}[/dim]")

    # 3. AI 總結與股票指標提取
    with console.status("[bold green]正在透過 Gemini AI 進行股票分析與提煉...[/bold green]"):
        try:
            summary_result = generate_summary(info, transcript_text, transcript_source=transcript_source)
        except Exception as e:
            msg = f"[{index}/{total}] [ERROR] Gemini AI 分析失敗 ({info['title']}): {e}"
            console.print(f"[bold red]❌ {msg}[/bold red]")
            logger.log(msg, level="ERROR")
            return "ERROR"

    # 4. 寫入 Markdown 筆記 (影片筆記/頻道名稱/<日期>_【股票代號名稱】_<標題>.md)
    tickers = summary_result.get('tickers', [])
    stock_name_zh = summary_result.get('stock_name_zh', '')
    note_path = save_note(info['channel'], info['upload_date'], info['title'], summary_result['final_md'], tickers=tickers, stock_name_zh=stock_name_zh)

    rel_note = note_path.relative_to(BASE_DIR)
    
    msg = f"[{index}/{total}] [SUCCESS] 筆記成功生成: {rel_note}"
    console.print(f"[bold green]✅ {msg}[/bold green]")
    logger.log(msg, level="INFO")

    # 5. 更新個股交叉索引
    if tickers:
        with console.status("[bold green]正在更新個股交叉索引...[/bold green]"):
            for t in tickers:
                rel_note_path = f"../影片筆記/{note_path.relative_to(BASE_DIR / '影片筆記')}".replace('\\', '/')
                update_stock_index(t, info, rel_note_path)
            console.print(f"  [bold magenta]📌 已更新 {len(tickers)} 個標的的交叉索引[/bold magenta]")

    # 記錄至已完成 processed_urls.txt，並自 no_subtitles_urls.txt 移除
    append_url_to_file(PROCESSED_URLS_FILE, url)
    remove_url_from_file(NO_SUBTITLES_FILE, url)
    return "SUCCESS"

def main():
    parser = argparse.ArgumentParser(description="YouTube 股票分析影片自動總結與索引工具")
    parser.add_argument("--url", type=str, help="單一 YouTube 影片網址")
    parser.add_argument("--file", type=str, help="包含網址列表的文字檔路徑 (預設為 urls.txt)")
    parser.add_argument("--process-no-subs", action="store_true", help="專門讀取並處理 no_subtitles_urls.txt 中無字幕的影片（啟動音訊轉譯）")
    parser.add_argument("--threads", type=int, default=None, help="指定 Faster-Whisper CPU 執行緒數量 (預設 16 全開)")
    parser.add_argument("--low-cpu", action="store_true", help="快捷降頻模式：自動將 CPU 執行緒限制為 4 核心以防滿載")
    args = parser.parse_args()

    threads_setting = 16
    if args.low_cpu:
        threads_setting = 4
    elif args.threads is not None:
        threads_setting = args.threads


    console.print(Panel.fit("[bold yellow]📈 YouTube 股票分析影片 AI 筆記系統[/bold yellow]\n[dim]頻道自動分類 × 投資結構化總結 × 即時股價與個股索引[/dim]"))
    logger.init_run()

    if not GEMINI_API_KEY:
        console.print("[bold red]⚠️ 警告: 未檢測到 GEMINI_API_KEY！[/bold red]")
        logger.log("未檢測到 GEMINI_API_KEY！", level="WARN")

    # 處理無字幕專用模式 (--process-no-subs)
    if args.process_no_subs:
        if not NO_SUBTITLES_FILE.exists() or not NO_SUBTITLES_FILE.read_text(encoding="utf-8").strip():
            console.print("[yellow]目前沒有暫存的無字幕影片 (no_subtitles_urls.txt 為空)。[/yellow]")
            return
            
        urls = [l.strip() for l in NO_SUBTITLES_FILE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        console.print(f"[bold magenta]🎙️ 啟動「無字幕音訊轉譯模式」，共有 {len(urls)} 部暫存影片待處理...[/bold magenta]")
        logger.log(f"啟動無字幕專用模式，處理 {len(urls)} 部暫存影片")
        
        success_cnt, error_cnt = 0, 0
        for idx, url in enumerate(urls, 1):
            console.print(f"\n[bold yellow]───────────── [{idx}/{len(urls)}] ─────────────[/bold yellow]")
            res = process_youtube_url(url, allow_audio_fallback=True, index=idx, total=len(urls), threads=threads_setting)
            if res == "SUCCESS":
                success_cnt += 1
            else:
                error_cnt += 1
            time.sleep(4)
            
        console.print(f"\n[bold green]🎉 無字幕影片轉譯完成！成功: {success_cnt}, 失敗: {error_cnt}[/bold green]\n")
        return

    # 常規模式
    input_file = Path(args.file) if args.file else (BASE_DIR / "urls.txt")
    urls = []
    if args.url:
        urls.append(args.url)
    elif input_file.exists():
        urls = [line.strip() for line in input_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    else:
        user_input = Prompt.ask("\n請輸入 YouTube 影片連結 (支援多個，請以空白隔開)")
        urls = [u.strip() for u in user_input.split() if u.strip()]

    if not urls:
        console.print("[yellow]未提供任何有效的網址。程式結束。[/yellow]")
        logger.finish_run(0, 0, 0, 0)
        return

    processed_set = get_processed_urls()
    
    success_cnt = 0
    skipped_no_cc_cnt = 0
    already_processed_cnt = 0
    processed_in_this_run = 0

    logger.log(f"讀取網址清單總數: {len(urls)} 個，已完成記錄檔數: {len(processed_set)} 個")

    for idx, url in enumerate(urls, 1):
        if url in processed_set:
            console.print(f"\n[dim]⏩ [{idx}/{len(urls)}] 網址已在 processed_urls.txt 中，跳過: {url}[/dim]")
            logger.log(f"[{idx}/{len(urls)}] [ALREADY_PROCESSED] 跳過已完成網址: {url}")
            already_processed_cnt += 1
            continue

        res = process_youtube_url(url, allow_audio_fallback=False, index=idx, total=len(urls), threads=threads_setting)

        if res == "SUCCESS":
            success_cnt += 1
        elif res == "SKIP_NO_CC":
            skipped_no_cc_cnt += 1
            
        processed_in_this_run += 1
        
        # 僅在還有後續影片時執行防封 IP 控制
        if idx < len(urls):
            # 1. 策略 A：隨機浮動延遲
            delay = round(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS), 1)
            console.print(f"  [dim]⏳ [隨機防風控] 暫停 {delay} 秒後處理下一部影片...[/dim]")
            time.sleep(delay)
            
            # 2. 策略 B：分批大休眠
            if processed_in_this_run > 0 and processed_in_this_run % BATCH_SIZE == 0:
                cooldown_min = BATCH_COOLDOWN_SECONDS // 60
                msg = f"💤 [分批冷卻] 已連續處理 {processed_in_this_run} 部影片，啟動防封 IP 休眠 {cooldown_min} 分鐘 ({BATCH_COOLDOWN_SECONDS}s)..."
                console.print(f"\n[bold yellow]{msg}[/bold yellow]")
                logger.log(msg, level="INFO")
                time.sleep(BATCH_COOLDOWN_SECONDS)

    logger.finish_run(len(urls), success_cnt, skipped_no_cc_cnt, already_processed_cnt)
    console.print("\n[bold green]🎉 任務處理完成！最新日誌已寫入 logs/latest.log 與 logs/run_日期.log[/bold green]\n")


if __name__ == "__main__":
    main()
