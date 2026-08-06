import sys
import io
import re
from pathlib import Path

# 強制 Windows 控制台使用 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
NOTES_DIR = BASE_DIR / "影片筆記"
OUTPUT_FILE = BASE_DIR / "no_subtitles_urls.txt"

def export_failed_urls():
    """
    掃描 影片筆記/ 目錄下所有逐字稿來源為「未能取得字幕」或「NO_CC」的研報，
    將其 YouTube 影片 URL 提煉出來並匯出至 no_subtitles_urls.txt 清單檔。
    """
    print("🔍 正在掃描影片筆記中逐字稿來源為「未能取得字幕」的研報...")
    
    failed_urls = []
    failed_notes = []

    for p in NOTES_DIR.rglob('*.md'):
        content = p.read_text(encoding='utf-8', errors='ignore')
        
        # 檢查逐字稿來源或內文關鍵字
        if 'NO_CC' in content or '未能取得字幕' in content or '語音轉譯失敗' in content or '未取得字幕' in content:
            # 優先匹配「- **影片連結**：[標題](URL)」格式
            url_match = re.search(r'- \*\*影片連結\*\*：\[.*?\]\((https?://[^\s\)]+)\)', content)
            if not url_match:
                url_match = re.search(r'(https?://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]+)', content)
                
            if url_match:
                url = url_match.group(1).strip()
                if url not in failed_urls:
                    failed_urls.append(url)
                    failed_notes.append((p.name, url))

    OUTPUT_FILE.write_text('\n'.join(failed_urls), encoding='utf-8')
    print(f"\n🎉 成功提煉 {len(failed_urls)} 個「未能取得字幕」的影片 URL！")
    print(f"📄 清單已儲存至: {OUTPUT_FILE.relative_to(BASE_DIR)}")

if __name__ == "__main__":
    export_failed_urls()
