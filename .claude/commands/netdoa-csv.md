# Netdoa NX CSV生成診断

よしやPOSシステムの CSV生成処理（ブラウザの3ステップチェーン）を確認・診断するタスク。

## ブラウザが行う3ステップチェーンの仕組み

ブラウザで「実行」ボタンを押したときの動作：

```
1. POST → ws_Entry=実行
      ↓ レスポンスに MTRV0010040 + openCsvWin() JavaScript が含まれる
2. GET  → ws_work_flg=1  （ポップアップウィンドウが開く）
      ↓ レスポンスに <BODY onLoad="document.CSV.submit()"> が含まれる
3. GET  → ws_work_flg=2  （ポップアップのonLoadで自動送信）
      ↓ 「CSVデータを作成します」と表示 → サーバー側でCSV生成開始
      ↓ ユーザーはポップアップを閉じるボタンで閉じる
```

**Pythonはこの3ステップをすべてHTTP GETで手動再現する。**  
JavaScriptを実行しないため、onLoadの自動送信をコードで代替する必要がある。

## `download.py` の `submit_csv_job()` で行っていること

`pos_system/download.py` の `submit_csv_job()` 関数（56行目）：

1. `session.get(cfg["csv_url"])` — セッション初期化
2. `session.post(...)` — フォーム送信（ws_Entry=実行）
3. レスポンスから `openCsvWin('...')` のURLを正規表現で抽出
4. そのURLに `session.get()` → ws_work_flg=1（step1）
5. レスポンスから `<FORM action="...">` と `<INPUT name="..." value="...">` を抽出
6. そのフォームのアクションに `session.get()` → ws_work_flg=2（step2）
7. step2レスポンスに「CSVデータを作成します」が含まれれば成功

## 診断スクリプト（チェーン全体を確認）

```python
# -*- coding: utf-8 -*-
import json, re, requests
from datetime import datetime
from pathlib import Path

cfg = json.loads(Path("pos_system/config.json").read_text(encoding="utf-8"))
BASE_URL = "https://www.netdoa-nx.jp"
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print("ログイン: OK")

# フォームGET → POST
target_date = "20260627"  # 確認したい日付に変更
s.get(cfg["csv_url"])
store_list = ",".join(str(i) for i in STORE_CODES)
submitted_at = datetime.now()
r = s.post(cfg["csv_url"], data={
    "ws_bussId": "6", "ws_stre_list": store_list,
    "ws_streCd": [str(i) for i in STORE_CODES],
    "ws_clsFlg": "3", "ws_clsFrom": "1", "ws_clsTo": "999999",
    "ws_clsNameFrom": "", "ws_clsNameTo": "",
    "ws_mdlclsFrom": "1", "ws_mdlclsTo": "999999",
    "ws_smlclsFrom": "", "ws_smlclsTo": "",
    "ws_dateFrom": target_date, "ws_dateTo": target_date,
    "ws_output_flg": "1", "ws_outFormat": "1",
    "ws_stre_sum_flg": "1", "ws_Entry": "実行",
})
html = r.content.decode("shift_jis", errors="replace")
print(f"POST: status={r.status_code}, MTRV0010040={'あり' if 'MTRV0010040' in html else 'なし'}")

# step1
m = re.search(r"openCsvWin\('([^']+)'", html)
if not m:
    print("openCsvWin URLなし → チェーン失敗")
    exit(1)

url1 = BASE_URL + m.group(1)
r1 = s.get(url1)
html1 = r1.content.decode("shift_jis", errors="replace")
has_onload = 'document.CSV.submit()' in html1
print(f"step1 (ws_work_flg=1): onLoad={'あり' if has_onload else 'なし'}")

if not has_onload:
    print("step1にonLoadなし → チェーン失敗")
    exit(1)

# step2
params = {}
for inp in re.finditer(r'<INPUT[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html1, re.I):
    params[inp.group(1)] = inp.group(2)
action_m = re.search(r'<FORM[^>]+action=["\']([^"\']+)["\']', html1, re.I)
action = action_m.group(1) if action_m else f"{BASE_URL}/MT/MTRV/MTRV0010040.php"
if not action.startswith("http"):
    action = BASE_URL + action

r2 = s.get(action, params=params)
html2 = r2.content.decode("shift_jis", errors="replace")
text2 = re.sub(r'<[^>]+>', ' ', html2)
text2 = re.sub(r'\s+', ' ', text2).strip()
print(f"step2 (ws_work_flg=2): {text2[:100]}")
print(f"送信時刻: {submitted_at.strftime('%H:%M:%S')} — 2〜5分後にDLページで確認してください")
```

## よくあるエラーと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| POSTでMTRV0010040なし | ログイン失敗、または日付指定ミス | ログインを再確認。日付は `YYYYMMDD` 形式 |
| openCsvWin URLなし | POSTが別ページに遷移している | レスポンスHTMLをダンプして内容確認 |
| step1にonLoadなし | 既に同じジョブが処理中 | 数分待ってから再試行 |
| step2で「CSVデータを作成します」が出ない | セッション切れ | 最初からやり直し（ログイン→POST→step1→step2） |
| 25分待ってもCSVが現れない | step2が届いていない | 診断スクリプトでチェーンを再確認 |

## DLページ確認

CSV生成後、`https://www.netdoa-nx.jp/DL/DL0010020.php` に  
`商品売上実績 (日別)` のリンクが現れる（作成時刻付き）。

`download.py` の `poll_and_download()` が2分ごとに最大25分間このページをポーリングする。

## 関連ファイル

- [pos_system/download.py](pos_system/download.py) — `submit_csv_job()`（56行目）、`poll_and_download()`（150行目）
- `pos_system/config.json` — `csv_url`、`download_dir`
