import sys
import io
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8 編碼以防止 cp950 編碼錯誤
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
URLS_FILE = BASE_DIR / "urls.txt"
PROCESSED_FILE = BASE_DIR / "processed_urls.txt"

def clean_urls():
    print("🧹 [獨立清理工具] 開始檢查 urls.txt 與 processed_urls.txt...")
    
    if not URLS_FILE.exists():
        print(f"❌ 找不到 urls.txt 檔案: {URLS_FILE}")
        return

    if not PROCESSED_FILE.exists():
        print(f"ℹ️ 找不到 processed_urls.txt 檔案，無需清理。")
        return

    # 讀取已處理完成了的 URL 集合
    processed_lines = PROCESSED_FILE.read_text(encoding="utf-8").splitlines()
    processed_set = set(l.strip() for l in processed_lines if l.strip() and not l.strip().startswith("#"))

    # 讀取原本 urls.txt
    urls_lines = URLS_FILE.read_text(encoding="utf-8").splitlines()
    
    original_count = 0
    cleaned_lines = []
    removed_count = 0

    for line in urls_lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append(line)
            continue
        if stripped.startswith("#"):
            cleaned_lines.append(line)
            continue

        original_count += 1
        if stripped in processed_set:
            removed_count += 1
        else:
            cleaned_lines.append(line)

    # 寫回清潔後的 urls.txt
    URLS_FILE.write_text("\n".join(cleaned_lines), encoding="utf-8")

    remaining_count = original_count - removed_count
    print(f"\n✅ urls.txt 清理完成！統計結果如下：")
    print(f"  • 原 urls.txt 網址總數：{original_count} 個")
    print(f"  • 已清理 (移除重複已完成)：{removed_count} 個")
    print(f"  • 剩餘未處理網址：{remaining_count} 個")

if __name__ == "__main__":
    clean_urls()

