# Windows 工作排程器每日凌晨 02:00 自動巡檢並執行 low-cpu 研報處理程序
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BaseDir = Split-Path -Parent $ScriptDir

Set-Location -Path $BaseDir

# 呼叫 Python 巡檢腳本並自動啟動 --low-cpu 處理程序
python "$ScriptDir\fetch_daily_new_videos.py" --auto-process
