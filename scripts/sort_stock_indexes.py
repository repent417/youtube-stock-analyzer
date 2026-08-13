import sys
import io
import re
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "個股索引"

def get_date_key(line_str: str) -> str:
    """提取每行紀錄的 [YYYY-MM-DD] 發布日期字串"""
    m = re.search(r'- \*\*\[(\d{4}-\d{2}-\d{2})\]\*\*', line_str)
    return m.group(1) if m else '0000-00-00'

def sort_index_content(content: str) -> str:
    """將個股索引內文中的 Timeline 分析紀錄按發布日期（最新在最上方）進行降序排序"""
    lines = content.splitlines()
    header_lines = []
    timeline_lines = []
    
    in_timeline = False
    for line in lines:
        if line.strip().startswith('## 📅 分析紀錄'):
            in_timeline = True
            header_lines.append(line)
        elif not in_timeline:
            header_lines.append(line)
        else:
            if line.strip().startswith('- **['):
                timeline_lines.append(line)
            elif line.strip():
                header_lines.append(line)
                
    # 按照日期降序排序 (最新在最上面)
    sorted_timeline = sorted(timeline_lines, key=get_date_key, reverse=True)
    
    result_lines = header_lines + sorted_timeline
    return "\n".join(result_lines) + "\n"

def main():
    print(f"🔍 開始進行全庫個股索引 Timeline 日期降序排序 (最新在最上面)...")
    
    if not INDEX_DIR.exists():
        print("⚠️ 找不到 個股索引/ 目錄！")
        return

    index_files = list(INDEX_DIR.glob("*.md"))
    updated_count = 0

    for idx_file in index_files:
        try:
            old_content = idx_file.read_text(encoding="utf-8", errors="ignore")
            new_content = sort_index_content(old_content)
            
            if old_content != new_content:
                idx_file.write_text(new_content, encoding="utf-8")
                updated_count += 1
        except Exception as e:
            print(f"❌ 處理 {idx_file.name} 失敗: {e}")

    print(f"\n🎉 排序完成！共掃描 {len(index_files)} 個個股索引檔，更新重排了 {updated_count} 個索引檔。")

if __name__ == "__main__":
    main()
