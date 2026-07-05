@echo off
:: Windowsタスクスケジューラに毎朝7時の自動実行を登録する
:: 管理者として実行してください

set TASK_NAME=POS_Daily_Download
set BAT_PATH=C:\one_tenri\OneDrive\HTY\vscode\pos_system\run_daily.bat

schtasks /create /tn "%TASK_NAME%" /tr "%BAT_PATH%" /sc DAILY /st 07:00 /f /rl HIGHEST

if %errorlevel% equ 0 (
    echo タスクスケジューラへの登録が完了しました。
    echo 毎朝 7:00 に自動でCSVダウンロードとDB取り込みが実行されます。
) else (
    echo 登録に失敗しました。管理者として実行してください。
)
pause
