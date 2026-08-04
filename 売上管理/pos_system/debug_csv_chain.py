# -*- coding: utf-8 -*-
"""
CSV生成チェーン診断スクリプト
step1・step2 で何が送受信されているかを詳細表示する
"""
import json, re, requests
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
cfg = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
BASE_URL = "https://www.netdoa-nx.jp"
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]

target_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
print(f"対象日付: {target_date}")

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ログイン
r = s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print(f"ログイン: {'OK' if 'PHPSESSID' in s.cookies else 'NG'}")

# GET → POST
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
    print("【エラー】openCsvWin URL が見つかりません")
    print("POSTレスポンス抜粋:")
    text = re.sub(r'<[^>]+>', ' ', html)
    print(re.sub(r'\s+', ' ', text).strip()[:300])
    exit(1)

url1 = BASE_URL + m.group(1)
print(f"step1 URL: {url1}")
r1 = s.get(url1)
html1 = r1.content.decode("shift_jis", errors="replace")
has_onload = 'document.CSV.submit()' in html1
print(f"step1 onLoad: {'あり' if has_onload else 'なし'}")

if not has_onload:
    print("【エラー】step1 に onLoad がありません")
    text1 = re.sub(r'<[^>]+>', ' ', html1)
    print(re.sub(r'\s+', ' ', text1).strip()[:300])
    exit(1)

# step2 パラメータ抽出（詳細表示）
params = {}
for inp in re.finditer(r'<INPUT[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html1, re.I):
    params[inp.group(1)] = inp.group(2)
print(f"step2 params: {params}")

action_m = re.search(r'<FORM[^>]+action=["\']([^"\']+)["\']', html1, re.I)
action = action_m.group(1) if action_m else f"{BASE_URL}/MT/MTRV/MTRV0010040.php"
if not action.startswith("http"):
    action = BASE_URL + action
print(f"step2 action: {action}")

r2 = s.get(action, params=params)
html2 = r2.content.decode("shift_jis", errors="replace")
text2 = re.sub(r'<[^>]+>', ' ', html2)
text2 = re.sub(r'\s+', ' ', text2).strip()
print(f"step2 レスポンス: {text2[:200]}")

print(f"\n送信時刻: {submitted_at.strftime('%H:%M:%S')}")
print("30秒後にDLページを確認します...")
import time; time.sleep(30)

# DLページ確認
DL_URL = f"{BASE_URL}/DL/DL0010020.php"
r3 = s.get(DL_URL)
html3 = r3.content.decode("shift_jis", errors="replace")
pattern = re.compile(
    r'<A HREF="(https://www\.netdoa-nx\.jp/download\.php\?[^"]+)"[^>]*>([^<]+)</A>',
    re.IGNORECASE,
)
links = list(pattern.finditer(html3))
print(f"\nDLページのリンク数: {len(links)}")
for m3 in links[:10]:
    print(f"  - {m3.group(2).strip()}")
