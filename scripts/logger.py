import datetime
from pathlib import Path
from config import LOGS_DIR

class TaskLogger:
    def __init__(self):
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        self.daily_log_path = LOGS_DIR / f"run_{today_str}.log"
        self.latest_log_path = LOGS_DIR / "latest.log"

    def log(self, message: str, level: str = "INFO"):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{now_str}] [{level}] {message}\n"
        
        # 寫入每日 Log
        with open(self.daily_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
            
        # 同步寫入 latest.log
        with open(self.latest_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)

    def init_run(self):
        """初始化新一次執行的 latest.log"""
        with open(self.latest_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== 最新執行紀錄 ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
            
        self.log("==================== 股票分析定時任務開始 ====================")

    def finish_run(self, total: int, success: int, skipped_no_cc: int, already_processed: int):
        self.log(f"==================== 任務完成摘要 ====================")
        self.log(f"總檢查網址數: {total}")
        self.log(f"成功生成筆記: {success} 部")
        self.log(f"跳過無 CC 字幕 (暫存 no_subtitles_urls.txt): {skipped_no_cc} 部")
        self.log(f"跳過先前已完成影片: {already_processed} 部")
        self.log("===================================================")

logger = TaskLogger()
