@echo off
:: Windowsタスクスケジューラに2時間ごと（9-19時）の自動実行を登録する
:: 管理者として実行してください

set TASK_NAME=よしや_メールチェック
set BAT_PATH=C:\one_tenri\OneDrive\HTY\vscode\メール処理\run_mail_check.bat

schtasks /create /tn "%TASK_NAME%" /tr "%BAT_PATH%" /sc DAILY /st 09:00 /ri 120 /du 10:00 /f /rl HIGHEST

if %errorlevel% equ 0 (
    echo タスクスケジューラへの登録が完了しました。
    echo 毎日9時から19時まで2時間ごとにメールチェックが実行されます。
) else (
    echo 登録に失敗しました。管理者として実行してください。
)
pause
