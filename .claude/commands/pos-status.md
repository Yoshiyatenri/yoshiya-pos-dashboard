# POSシステム 現状確認

よしやPOSシステムの現在の状態を確認するタスク。

## 確認項目

以下を順番に確認して結果を報告すること：

### 1. ダウンロード済みCSVの一覧
```powershell
Get-ChildItem pos_system\downloads\*.csv | Sort-Object Name | Select-Object Name, Length, LastWriteTime
```

### 2. データベースの件数・最新日付
```python
import sqlite3
con = sqlite3.connect("pos_system/pos_data.db")
print("総件数:", con.execute("SELECT COUNT(*) FROM sales").fetchone()[0])
print("最新日付:", con.execute("SELECT MAX(pos_date) FROM sales").fetchone()[0])
print("最古日付:", con.execute("SELECT MIN(pos_date) FROM sales").fetchone()[0])
rows = con.execute("SELECT pos_date, COUNT(*) FROM sales GROUP BY pos_date ORDER BY pos_date DESC LIMIT 7").fetchall()
print("\n直近7日の件数:")
for d, c in rows:
    print(f"  {d}: {c:,}件")
con.close()
```

### 3. 最新ログの確認
```powershell
Get-ChildItem pos_system\logs\daily_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content -Tail 20
```

### 4. タスクスケジューラの状態
```powershell
Get-ScheduledTask -TaskName "よしや_POS日次処理" | Select-Object TaskName, State, @{N="LastRun";E={$_.LastRunTime}}, @{N="NextRun";E={$_.NextRunTime}}
```

結果をまとめて「正常」「要確認」「エラー」のいずれかで総合判定すること。
