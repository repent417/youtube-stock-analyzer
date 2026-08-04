import os
import re
from pathlib import Path
from dotenv import load_dotenv

# 載入 .env 檔案
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 主要目錄結構設定
NOTES_DIR = BASE_DIR / "影片筆記"
INDEX_DIR = BASE_DIR / "個股索引"
TRANSCRIPTS_DIR = BASE_DIR / "原始字幕"
SCRIPTS_DIR = BASE_DIR / "scripts"
LOGS_DIR = BASE_DIR / "logs"
NO_SUBTITLES_FILE = BASE_DIR / "no_subtitles_urls.txt"
PROCESSED_URLS_FILE = BASE_DIR / "processed_urls.txt"

# 確保目錄存在
for d in [NOTES_DIR, INDEX_DIR, TRANSCRIPTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# GEMINI API 金鑰
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def sanitize_filename(name: str) -> str:
    """清理檔案與資料夾名稱中的非法字元 (Windows / Linux 相容)"""
    # 移除 Windows 檔名不允許的字元 \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 移除多餘空白
    cleaned = cleaned.strip()
    return cleaned if cleaned else "未命名"
