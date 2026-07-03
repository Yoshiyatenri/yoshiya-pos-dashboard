@echo off
:: ダッシュボードをブラウザで開く
set PYTHON=C:\Users\Koki\AppData\Local\Programs\Python\Python312\python.exe
set STREAMLIT=C:\Users\Koki\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe
set DIR=C:\one_tenri\OneDrive\HTY\vscode\pos_system

cd /d "%DIR%"
"%STREAMLIT%" run dashboard.py --server.port 8501 --server.headless false
