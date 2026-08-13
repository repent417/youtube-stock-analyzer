from pathlib import Path
from config import INDEX_DIR, sanitize_filename
from stock_market import normalize_ticker, get_clean_stock_info

def update_stock_index(ticker: str, video_info: dict, note_rel_path: str):
    """
    更新或建立個股交叉索引 Markdown 檔案：
    台股: 個股索引/<代號>_<中文股名>.md (例如 2337_旺宏.md)
    美股: 個股索引/<Ticker>_<名稱>.md (例如 NVDA_輝達.md)
    """
    norm_ticker = normalize_ticker(ticker)
    code, clean_name = get_clean_stock_info(ticker)
    
    # 組合索引檔名: 2337_旺宏.md 或 NVDA_輝達.md
    if clean_name and clean_name != code:
        index_filename = f"{code}_{clean_name}.md"
    else:
        index_filename = f"{code}.md"
        
    clean_filename = sanitize_filename(index_filename)
    if not clean_filename.endswith(".md"):
        clean_filename += ".md"
        
    index_file = INDEX_DIR / clean_filename
    
    # 檢查並遷移舊格式索引檔 (如 2337.TW.md)
    old_file_tw = INDEX_DIR / f"{sanitize_filename(norm_ticker)}.md"
    old_file_code = INDEX_DIR / f"{sanitize_filename(code)}.md"
    
    for old_file in [old_file_tw, old_file_code]:
        if old_file.exists() and old_file != index_file:
            print(f"🔄 自動重命名索引檔: {old_file.name} ➔ {index_file.name}")
            try:
                if index_file.exists():
                    old_content = old_file.read_text(encoding="utf-8")
                    old_file.unlink()
                else:
                    old_file.rename(index_file)
            except Exception as e:
                print(f"⚠️ 重命名舊索引檔失敗: {e}")

    date_str = video_info['upload_date']
    title = video_info['title']
    channel = video_info['channel']
    note_stem = Path(note_rel_path).stem
    
    # 使用 Obsidian 原生雙括號 [[檔名|顯示標題]]，防止資料夾路徑含空白或特殊字元導致跳轉失敗
    entry = f"- **[{date_str}]** [[{note_stem}|{title}]] （頻道：`{channel}`）\n"
    
    display_title = f"{code} {clean_name}" if clean_name != code else code
    
    if not index_file.exists():
        header = f"""# 個股歷史分析索引：{display_title}

本檔案由自動化系統維護，彙整所有提及 {display_title} 的 YouTube 股票分析影片筆記。

---

## 📅 分析紀錄 (Timeline)
"""
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(header + entry)
    else:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        if note_stem not in content:
            raw_new = content + entry
            from sort_stock_indexes import sort_index_content
            sorted_new = sort_index_content(raw_new)
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(sorted_new)


