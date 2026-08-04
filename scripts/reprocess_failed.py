import sys
import io
import time
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from yt_extractor import get_video_info, extract_video_id, get_transcript, save_transcript
from summarizer import generate_summary, save_note
from stock_indexer import update_stock_index
from config import BASE_DIR, TRANSCRIPTS_DIR

console = Console(force_terminal=True)

def main():
    urls_file = BASE_DIR / "urls.txt"
    if not urls_file.exists():
        console.print("[red]❌ 找不到 urls.txt 檔案[/red]")
        return
        
    urls = [line.strip() for line in urls_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    
    # 搜尋原始字幕中有 "未能取得字幕" 的項目
    failed_urls = []
    
    with console.status("[bold green]正在比對缺失字幕的影片...[/bold green]"):
        for url in urls:
            vid = extract_video_id(url)
            if not vid:
                continue
            
            # 檢查是否有對應的 txt 檔且包含未能取得字幕字樣
            is_failed = False
            for txt_path in TRANSCRIPTS_DIR.glob("**/*.txt"):
                txt_content = txt_path.read_text(encoding="utf-8", errors="ignore")
                if "未能取得字幕" in txt_content:
                    info = get_video_info(url)
                    if info.get('id') == vid:
                        is_failed = True
                        break
            if is_failed:
                failed_urls.append((url, info))

    console.print(f"\n[bold yellow]🔍 發現共 {len(failed_urls)} 部無字幕影片，準備進行 Gemini AI 音訊轉譯 (Audio Transcription)...[/bold yellow]\n")

    for idx, (url, info) in enumerate(failed_urls, 1):
        console.print(f"[bold cyan]─────── [{idx}/{len(failed_urls)}] 轉譯中: {info['title']} ───────[/bold cyan]")
        
        # 1. 執行音訊轉譯
        transcript_data = get_transcript(info['id'], url)
        transcript_text = transcript_data['text']
        transcript_source = transcript_data['source']
        
        console.print(f"  [bold green]標籤:[/bold green] {transcript_source}")
        
        # 2. 更新原始字幕 txt 備份
        save_transcript(info['channel'], info['upload_date'], info['title'], transcript_text)
        
        # 3. 重新由 AI 生成詳細 Markdown 總結
        summary_result = generate_summary(info, transcript_text, transcript_source=transcript_source)
        
        # 4. 更新 Markdown 筆記檔
        tickers = summary_result.get('tickers', [])
        note_path = save_note(info['channel'], info['upload_date'], info['title'], summary_result['final_md'], tickers=tickers)
        console.print(f"  [bold green]✅ 筆記已成功更新:[bold green] [underline]{note_path.relative_to(BASE_DIR)}[/underline]")
        
        # 5. 更新個股索引
        if tickers:
            for t in tickers:
                rel_note_path = f"../影片筆記/{note_path.relative_to(BASE_DIR / '影片筆記')}".replace('\\', '/')
                update_stock_index(t, info, rel_note_path)
                
        time.sleep(5)

    except Exception as e:
        err_str = str(e)
        if "GenerateRequestsPerDayPerProjectPerModel" in err_str or "20" in err_str:
            console.print("\n[bold yellow]ℹ️ 已達今日免費 Gemini API 呼叫次數上限 (20次/天)。[/bold yellow]")
            console.print("[yellow]系統已保存進度。請於明日 API 額度重置後，再次執行 `python scripts/reprocess_failed.py` 即可自動繼續轉譯剩餘影片！[/yellow]\n")
        else:
            console.print(f"\n[bold red]❌ 執行過程中發生錯誤: {e}[/bold red]\n")

if __name__ == "__main__":
    main()

