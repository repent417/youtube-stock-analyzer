import subprocess
import sys
from pathlib import Path
from config import BASE_DIR, SCRIPTS_DIR

def register_daily_2am_task():
    ps_script = SCRIPTS_DIR / "daily_nightly_runner.ps1"
    tr_val = f'powershell.exe -ExecutionPolicy Bypass -File "{ps_script}"'
    
    cmd = [
        'schtasks', '/Create',
        '/TN', 'YouTubeStockAnalyzerDaily2AM',
        '/TR', tr_val,
        '/SC', 'DAILY',
        '/ST', '02:00',
        '/F'
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='cp950', errors='ignore')
    if res.returncode == 0:
        print("SUCCESS: 成功註冊 Windows 工作排程器: 每日早上 02:00 自動巡檢與 Low CPU 處理！")
    else:
        print(f"WARNING: 註冊排程失敗 (ReturnCode {res.returncode}): {res.stderr or res.stdout}")

if __name__ == "__main__":
    register_daily_2am_task()
