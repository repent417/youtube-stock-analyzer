import argparse
import sys
import io
import re
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.panel import Panel

from config import (
    BASE_DIR, 
    NOTES_DIR, 
    TRANSCRIPTS_DIR, 
    INDEX_DIR, 
    PROCESSED_URLS_FILE, 
    NO_SUBTITLES_FILE
)
from main import process_youtube_url

console = Console(force_terminal=True)
REPROCESS_URLS_FILE = BASE_DIR / "reprocess_urls.txt"

class VaultCache:
    """單次全庫快取載入器 (Single-Pass Cache)，將幾萬次磁碟 I/O 降至一次全庫讀取"""
    def __init__(self):
        start_t = time.time()
        with console.status("[bold green]⚡ 正在進行單次記憶體快取載入 (Single-Pass Cache)...[/bold green]"):
            # 1. 研報快取
            self.notes = []
            for p in NOTES_DIR.rglob('*.md'):
                try:
                    self.notes.append({'path': p, 'stem': p.stem, 'content': p.read_text(encoding='utf-8', errors='ignore')})
                except Exception:
                    pass

            # 2. 字幕檔索引 (stem -> Path)
            self.transcripts = {}
            for p in TRANSCRIPTS_DIR.rglob('*.txt'):
                self.transcripts[p.stem] = p

            # 3. 個股索引快取
            self.indexes = []
            for p in INDEX_DIR.glob('*.md'):
                try:
                    self.indexes.append({'path': p, 'stem': p.stem, 'content': p.read_text(encoding='utf-8', errors='ignore')})
                except Exception:
                    pass
                    
        elapsed = time.time() - start_t
        console.print(f"  [dim]⚡ 成功加載 {len(self.notes)} 篇研報, {len(self.transcripts)} 篇字幕, {len(self.indexes)} 個索引 (耗時: {elapsed:.2f}s)[/dim]")

def remove_url_from_txt(file_path: Path, url: str):
    """自 txt 檔案移除指定的 URL"""
    if file_path.exists():
        lines = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if url in lines:
            lines.remove(url)
            file_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

def cleanup_old_url_artifacts(url: str, cache: VaultCache, dry_run: bool = False):
    """
    於記憶體中極速比對 (In-Memory Lookup)，並刪除指定 URL 的舊有 Markdown 筆記、逐字稿與個股索引條目
    """
    deleted_notes = []
    deleted_transcripts = []
    modified_indexes = []
    deleted_indexes = []

    # 1. 記憶體中極速搜尋研報與字幕 (< 0.001s)
    for note in cache.notes:
        if url in note['content']:
            deleted_notes.append(note['path'])
            if note['stem'] in cache.transcripts:
                deleted_transcripts.append(cache.transcripts[note['stem']])

    # 2. 記憶體中極速搜尋並處理個股索引
    for note_path in deleted_notes:
        note_stem = note_path.stem
        for idx in cache.indexes:
            if note_stem in idx['content']:
                lines = idx['content'].splitlines()
                new_lines = [l for l in lines if note_stem not in l]
                new_content = "\n".join(new_lines) + "\n"
                
                # 同步更新快取
                idx['content'] = new_content
                
                has_remaining = any(l.strip().startswith('- **[') for l in new_lines)
                if not has_remaining:
                    if idx['path'] not in deleted_indexes:
                        deleted_indexes.append(idx['path'])
                else:
                    modified_indexes.append((idx['path'], new_content))

    if dry_run:
        console.print(f"\n[bold yellow]🔍 [DRY-RUN 預覽] URL: {url}[/bold yellow]")
        console.print(f"  - 將刪除筆記: {[p.name for p in deleted_notes]}")
        console.print(f"  - 將刪除字幕: {[p.name for p in deleted_transcripts]}")
        console.print(f"  - 將清理個股索引: {list(set([p.name for p, _ in modified_indexes]))}")
        console.print(f"  - 將刪除空個股索引: {[p.name for p in deleted_indexes]}")
        return


    # 3. 執行實際刪除
    for p in deleted_notes:
        if p.exists():
            p.unlink()
            console.print(f"  [dim]🗑️ 已刪除舊研報: {p.name}[/dim]")

    for p in deleted_transcripts:
        if p.exists():
            p.unlink()
            console.print(f"  [dim]🗑️ 已刪除舊字幕: {p.name}[/dim]")

    for idx_path, new_content in modified_indexes:
        if idx_path.exists():
            idx_path.write_text(new_content, encoding='utf-8')
            console.print(f"  [dim]✏️ 已清理個股索引條目: {idx_path.name}[/dim]")

    for idx_path in deleted_indexes:
        if idx_path.exists():
            idx_path.unlink()
            console.print(f"  [dim]🗑️ 已刪除空個股索引: {idx_path.name}[/dim]")

    # 4. 從歷史解鎖檔案移除此 URL
    remove_url_from_txt(PROCESSED_URLS_FILE, url)
    remove_url_from_txt(NO_SUBTITLES_FILE, url)
    console.print(f"  [bold green]🔓 已將 URL 從 processed_urls.txt 與 no_subtitles_urls.txt 解鎖！[/bold green]")

def main():
    parser = argparse.ArgumentParser(description="YouTube 股票分析影片「特定網址重跑與重新轉譯」全自動化腳本 (極速快取版)")
    parser.add_argument("--url", type=str, help="單一欲重跑的 YouTube 影片網址")
    parser.add_argument("--file", type=str, help="包含欲重跑網址清單的文字檔 (預設為 reprocess_urls.txt)")
    parser.add_argument("--dry-run", action="store_true", help="僅預覽要刪除與清理的舊檔案，不實際執行")
    parser.add_argument("--use-gpu", "--gpu", action="store_true", help="啟用 Intel Iris Xe GPU 顯卡轉譯加速模式")
    parser.add_argument("--threads", type=int, default=None, help="指定 Faster-Whisper CPU 執行緒數量 (預設 16)")
    parser.add_argument("--low-cpu", action="store_true", help="快捷降頻模式：自動限制 CPU 執行緒為 4 核心")
    args = parser.parse_args()

    threads_setting = 16
    if args.low_cpu:
        threads_setting = 4
    elif args.threads is not None:
        threads_setting = args.threads

    console.print(Panel.fit("[bold yellow]🔄 YouTube 影片特定網址重跑與轉譯系統 (極速快取版)[/bold yellow]\n[dim]單次快取載入 × 解鎖 URL × Faster-Whisper 全自動語音轉譯與研報重新生成[/dim]"))

    input_file = Path(args.file) if args.file else REPROCESS_URLS_FILE
    urls = []
    if args.url:
        urls.append(args.url.strip())
    elif input_file.exists():
        urls = [l.strip() for l in input_file.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]

    if not urls:
        console.print(f"[yellow]未發現任何待重跑的 URL。請在 {REPROCESS_URLS_FILE.name} 貼入網址或使用 --url <網址> 執行。[/yellow]")
        return

    # 啟動單次全庫快取載入
    cache = VaultCache()

    console.print(f"[bold cyan]🎯 本次共有 {len(urls)} 個 URL 進入重跑處理佇列...[/bold cyan]")

    for idx, url in enumerate(urls, 1):
        console.print(f"\n[bold yellow]───────────── 重跑 [{idx}/{len(urls)}] ─────────────[/bold yellow]")
        
        # 1. 舊檔與紀錄連動清理 (記憶體極速比對)
        cleanup_old_url_artifacts(url, cache, dry_run=args.dry_run)

        if args.dry_run:
            continue

        # 2. 重新執行 Faster-Whisper 轉譯與研報生成
        res = process_youtube_url(url, index=idx, total=len(urls), threads=threads_setting, use_gpu=args.use_gpu)
        
        # 3. 從重跑佇列檔中清除已完成的網址
        if res == "SUCCESS" and input_file.exists():
            remove_url_from_txt(input_file, url)

    if not args.dry_run:
        console.print(f"\n[bold green]🎉 佇列中的 {len(urls)} 個網址已重跑完成！相關研報與個股索引已全新更新。[/bold green]\n")

if __name__ == "__main__":
    main()
