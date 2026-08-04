# Windows 工作排程器每日夜間 23:00 自動執行腳本
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BaseDir = Split-Path -Parent $ScriptDir

Set-Location -Path $BaseDir

# 呼叫 Python 主程式執行預設批次處理
python "$ScriptDir\main.py"
