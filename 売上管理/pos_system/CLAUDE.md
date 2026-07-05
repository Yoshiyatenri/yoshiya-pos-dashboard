# よしや POS システム — CLAUDE.md

## プロジェクト概要
「お菓子のデパート よしや」（関西約22店舗）のPOSデータ自動収集・分析システム。

```
Netdoa NX (Web POS) → download.py → downloads/*.csv → import_db.py → pos_data.db → dashboard.py (Streamlit)
```

毎朝07:00 に Windowsタスクスケジューラが `run_daily.py` を起動して前日データを自動取り込み。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `run_daily.py` | タスクスケジューラから呼ばれるエントリポイント。download → import を順に実行 |
| `download.py` | Netdoa NX にログインしてCSVジョブを送信・ポーリング・ダウンロード |
| `import_db.py` | CSVを読み込み SQLite (`pos_data.db`) に INSERT OR IGNORE で取り込む |
| `dashboard.py` | Streamlit + Plotly のダッシュボード |
| `config.json` | 認証情報・URLなど（**Gitに含めない**） |
| `pos_data.db` | SQLite DB。salesテーブルに全売上データ |
| `downloads/` | ダウンロードしたCSV置き場（YYYYMMDD.csv 形式） |
| `logs/` | 月別ログ（download_YYYYMM.log, daily_YYYYMM.log, import_YYYYMM.log） |
| `check_*.py` / `debug_*.py` | 診断・デバッグ用スクリプト（本番では使わない） |

---

## Netdoa NX API — 重要な技術知識

### ログイン
- URL: `config.json["login_url"]`（`/0010010.php`）
- POST: `ws_userId`, `ws_pswd`, `ws_savePswd=1`, `ws_actType=1`
- 成功判定: `PHPSESSID` が `session.cookies` に入る

### CSV生成ジョブ送信（`/MT/MTRV/MTRV0010010.php?ws_bussId=6`）
ブラウザが行う3ステップチェーンをPythonで再現する：
1. **GET** でフォームページを取得（サーバーセッション初期化）
2. **POST** でジョブをキューに入れる（レスポンスに `MTRV0010040` + `openCsvWin()` JS が含まれる）
3. **GET** `ws_work_flg=1` — ポップアップを開く（`<BODY onLoad="document.CSV.submit()">` が含まれる）
4. **GET** `ws_work_flg=2` — onLoad の自動送信を再現 → 「CSVデータを作成します」が表示されれば成功

成功レスポンス: HTML内に `MTRV0010040` が含まれる。

### CSVダウンロードページ（`/DL/DL0010020.php`）
- リンクテキスト例: `商品売上実績 (日別) (店舗別) [2026/06/26〜2026/06/26] 作成日[2026/06/27 07:01:23]`
- 「商品売上実績」かつ「日別」を含むリンクのみ対象（他レポートを誤取得しない）
- 生成まで通常1〜10分。最大25分ポーリング（2分間隔）

### 文字コード
Netdoa NX のすべてのHTMLレスポンスは **Shift-JIS**。
```python
html = r.content.decode("shift_jis", errors="replace")
```

---

## 店舗コード
```python
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
```
（4番は欠番。100は本部または特殊店舗）

ダッシュボードの店舗名表示では `"お菓子のデパートよしや"` プレフィックスを除去して短縮名を使う。

---

## データベース（SQLite）

テーブル: `sales`  
UNIQUE制約: `(pos_date, store_code, plu_code)` — 重複インポートは自動スキップ  
主なカラム: `pos_date` (TEXT, YYYY-MM-DD), `store_code`, `store_name`, `plu_code`, `plu_name`, `sales_amount`, `sales_qty`, `gross_profit` など全36カラム

---

## 実行方法

```powershell
# 前日分を手動実行
python run_daily.py

# 特定日付を指定してダウンロードのみ
python download.py 20260625

# 特定CSVをDBに取り込み
python import_db.py downloads/20260625.csv

# ダッシュボード起動
streamlit run dashboard.py
```

---

## 設定ファイル（config.json の構造）
```json
{
  "login_url": "...",
  "csv_url": "...",
  "user_id": "...",
  "password": "...",
  "download_dir": "downloads",
  "db_path": "pos_data.db",
  "run_time": "07:00"
}
```
`config.json` は認証情報を含むため `.gitignore` に追加すること。

---

## タスクスケジューラ登録済み

| タスク名 | トリガー | 役割 |
|---|---|---|
| `よしや_POS日次処理` | 毎日 07:00 / StartWhenAvailable=True | 通常の定期実行 |
| `yoshiya_POS_logon` | ログイン時（毎回） | PC起動時に未取得分を補完 |

**実行ファイル:** `C:\one_tenri\OneDrive\HTY\vscode\売上管理\pos_system\run_daily.py`  
**作業ディレクトリ:** `C:\one_tenri\OneDrive\HTY\vscode\売上管理\pos_system`

タスク再登録コマンド（管理者PowerShellで直接入力、スクリプトファイル経由は文字化けするため不可）:
```powershell
$a = New-ScheduledTaskAction -Execute "C:\Users\Koki\AppData\Local\Programs\Python\Python312\python.exe" -Argument "C:\one_tenri\OneDrive\HTY\vscode\売上管理\pos_system\run_daily.py" -WorkingDirectory "C:\one_tenri\OneDrive\HTY\vscode\売上管理\pos_system"
$p = New-ScheduledTaskPrincipal -UserId "Koki" -LogonType Interactive -RunLevel Highest
$s1 = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 72)
Register-ScheduledTask -TaskName "よしや_POS日次処理" -Action $a -Trigger (New-ScheduledTaskTrigger -Daily -At "07:00") -Settings $s1 -Principal $p -Force
$s2 = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "yoshiya_POS_logon" -Action $a -Trigger (New-ScheduledTaskTrigger -AtLogOn -User "Koki") -Settings $s2 -Principal $p -Force
```
