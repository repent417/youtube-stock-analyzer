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

from config import GEMINI_API_KEY, BASE_DIR, NO_SUBTITLES_FILE
from yt_extractor import get_video_info, extract_video_id, get_transcript, save_transcript
from summarizer import generate_summary, save_note
from stock_indexer import update_stock_index

console = Console(force_terminal=True)

def append_no_subtitle_url(url: str):
    """追加無字幕影片 URL 至 no_subtitles_urls.txt (自動去重)"""
    existing_urls = []
    if NO_SUBTITLES_FILE.exists():
        existing_urls = [l.strip() for l in NO_SUBTITLES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        
    if url not in existing_urls:
        existing_urls.append(url)
        NO_SUBTITLES_FILE.write_text("\n".join(existing_urls), encoding="utf-8")

def remove_no_subtitle_url(url: str):
    """自 no_subtitles_urls.txt 移除已成功處理的 URL"""
    if NO_SUBTITLES_FILE.exists():
        existing_urls = [l.strip() for l in NO_SUBTITLES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
        if url in existing_urls:
            existing_urls.remove(url)
            NO_SUBTITLES_FILE.write_text("\n".join(existing_urls), encoding="utf-8")

def process_youtube_url(url: str, allow_audio_fallback: bool = False) -> bool:
    """
    處理單一 YouTube URL
    allow_audio_fallback: 
      - False (預設常規模式): 無 CC 字幕時直接跳過，記錄至 no_subtitles_urls.txt
      - True (無字幕專用模式): 無 CC 字幕時啟動 Gemini 音訊轉譯
    """
    console.print(f"\n[bold cyan]🚀 開始處理 YouTube 影片:[/bold cyan] {url}")
    
    video_id = extract_video_id(url)
    if not video_id:
        console.print(f"[bold red]❌ 無法解析 YouTube 影片 ID: {url}[/bold red]")
        return False

    # 1. 抓取影片元資料
    with console.status("[bold green]正在抓取影片資訊 (標題, 頻道, 日期)...[/bold green]"):
        try:
            info = get_video_info(url)
            console.print(f"  [bold gold1]頻道:[/bold gold1] {info['channel']}")
            console.print(f"  [bold gold1]標題:[/bold gold1] {info['title']}")
            console.print(f"  [bold gold1]日期:[/bold gold1] {info['upload_date']}")
        except Exception as e:
            console.print(f"[bold red]❌ 抓取影片資訊失敗: {e}[/bold red]")
            return False

    # 2. 檢查與抓取字幕
    with console.status("[bold green]正在檢查字幕狀態...[/bold green]"):
        transcript_data = get_transcript(video_id, url, allow_audio_fallback=allow_audio_fallback)
        
    # 若不允許音訊轉譯且無 CC 字幕 ➔ 暫存 URL 並跳過
    if not transcript_data['has_cc'] and not allow_audio_fallback:
        append_no_subtitle_url(url)
        console.print(f"  [bold yellow]ℹ️ 影片無預設 CC 字幕，已將網址暫存至 no_subtitles_urls.txt，跳過此影片（消耗 0 次 API）[/bold yellow]")
        return False

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
            console.print(f"[bold red]❌ Gemini AI 分析失敗: {e}[/bold red]")
            return False

    # 4. 寫入 Markdown 筆記 (影片筆記/頻道名稱/<日期>_【股票代號名稱】_<標題>.md)
    tickers = summary_result.get('tickers', [])
    note_path = save_note(info['channel'], info['upload_date'], info['title'], summary_result['final_md'], tickers=tickers)
    console.print(f"[bold green]✅ 影片筆記已成功生成:[bold green] [bold underline]{note_path.relative_to(BASE_DIR)}[/bold underline]")

    # 5. 更新個股交叉索引
    if tickers:
        with console.status("[bold green]正在更新個股交叉索引...[/bold green]"):
            for t in tickers:
                rel_note_path = f"../影片筆記/{note_path.relative_to(BASE_DIR / '影片筆記')}".replace('\\', '/')
                update_stock_index(t, info, rel_note_path)
            console.print(f"  [bold magenta]📌 已更新 {len(tickers)} 個標的的交叉索引[/bold magenta]")

    # 若順利完成且原先在 no_subtitles_urls.txt 中，將其移除
    remove_no_subtitle_url(url)
    return True

def main():
    parser = argparse.ArgumentParser(description="YouTube 股票分析影片自動總結與索引工具")
    parser.add_argument("--url", type=str, help="單一 YouTube 影片網址")
    parser.add_argument("--file", type=str, help="包含網址列表的文字檔路徑 (每行一個 URL)")
    parser.add_argument("--process-no-subs", action="store_true", help="專門讀取並處理 no_subtitles_urls.txt 中無字幕的影片（啟動音訊轉譯）")
    args = parser.parse_args()

    console.print(Panel.fit("[bold yellow]📈 YouTube 股票分析影片 AI 筆記系統[/bold yellow]\n[dim]頻道自動分類 × 投資結構化總結 × 即時股價與個股索引[/dim]"))

    if not GEMINI_API_KEY:
        console.print("[bold red]⚠️ 警告: 未檢測到 GEMINI_API_KEY！[/bold red]")
        console.print("請在 `g:\\我的雲端硬碟\\股票分析\\.env` 檔案中加入：GEMINI_API_KEY=your_actual_key\n")

    # 處理無字幕專用模式
    if args.process_no_subs:
        if not NO_SUBTITLES_FILE.exists() or not NO_SUBTITLES_FILE.read_text(encoding="utf-8").strip():
            console.print("[yellow]目前沒有暫存的無字幕影片 (no_subtitles_urls.txt 為空)。[/yellow]")
            return
            
        urls = [l.strip() for l in NO_SUBTITLES_FILE.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        console.print(f"[bold magenta]🎙️ 啟動「無字幕音訊轉譯模式」，共有 {len(urls)} 部暫存影片待處理...[/bold magenta]")
        for idx, url in enumerate(urls, 1):
            console.print(f"\n[bold yellow]───────────── [{idx}/{len(urls)}] ─────────────[/bold yellow]")
            process_youtube_url(url, allow_audio_fallback=True)
            time.sleep(4)
        console.print("\n[bold green]🎉 無字幕影片批次轉譯完成！[/bold green]\n")
        return

    urls = []
    if args.url:
        urls.append(args.url)
    elif args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            console.print(f"[bold red]❌ 找不到檔案: {args.file}[/bold red]")
            return
    else:
        user_input = Prompt.ask("\n請輸入 YouTube 影片連結 (支援多個，請以空白隔開)")
        urls = [u.strip() for u in user_input.split() if u.strip()]

    if not urls:
        console.print("[yellow]未提供任何有效的網址。程式結束。[/yellow]")
        return

    for idx, url in enumerate(urls, 1):
        console.print(f"\n[bold yellow]───────────── [{idx}/{len(urls)}] ─────────────[/bold yellow]")
        process_youtube_url(url, allow_audio_fallback=False)
        time.sleep(3)

    console.print("\n[bold green]🎉 全部任務處理完成！[/bold green]\n")

if __name__ == "__main__":
    main()
