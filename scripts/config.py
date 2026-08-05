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

# DeepSeek API 設定
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 地端 LLM 與 語音轉譯設定
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
WHISPER_MODEL_SIZE = "small"  # 亦可改為 "medium" 或 "base"

# 防封 IP 頻率控制設定 (Strategy A + B)
MIN_DELAY_SECONDS = 6      # 單部影片最少隨機停頓秒數
MAX_DELAY_SECONDS = 12     # 單部影片最多隨機停頓秒數
BATCH_SIZE = 30            # 分批門檻：每處理 N 部影片
BATCH_COOLDOWN_SECONDS = 180  # 分批大休眠秒數 (180s = 3分鐘)




# GEMINI API 金鑰
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def sanitize_filename(name: str) -> str:
    """清理檔案與資料夾名稱中的非法字元 (Windows / Linux 相容)"""
    # 移除 Windows 檔名不允許的字元 \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 移除多餘空白
    cleaned = cleaned.strip()
    return cleaned if cleaned else "未命名"
