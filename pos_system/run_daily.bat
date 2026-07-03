@echo off
:: 毎朝自動実行: NetdoaからCSVをダウンロードしてDBに取り込む
set PYTHON=C:\Users\Koki\AppData\Local\Programs\Python\Python312\python.exe
set DIR=C:\one_tenri\OneDrive\HTY\vscode\pos_system

cd /d "%DIR%"

echo [%date% %time%] 開始 >> logs\task.log
%PYTHON% download.py >> logs\task.log 2>&1
if %errorlevel% neq 0 (
    echo [%date% %time%] ダウンロード失敗 >> logs\task.log
    exit /b 1
)
%PYTHON% import_db.py >> logs\task.log 2>&1
echo [%date% %time%] 完了 >> logs\task.log
