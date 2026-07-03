"""
フォーム送信の0バイト問題を詳細診断
"""
import json, re, requests
from urllib.parse import urlencode

cfg = json.load(open("config.json", encoding="utf-8"))
BASE = "https://www.netdoa-nx.jp"
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ログイン
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print(f"ログイン後クッキー: {list(s.cookies.keys())}")

# POST（ジョブ送信）
r2 = s.post(cfg["csv_url"], data={
    "ws_streCd":      [str(i) for i in STORE_CODES],
    "ws_dateFrom":    "20260625",
    "ws_dateTo":      "20260625",
    "ws_output_flg":  "1",
    "ws_outFormat":   "1",
    "ws_stre_sum_flg":"1",
    "ws_bussId":      "6",
    "ws_Entry":       "実行",
    "ws_clsFlg": "", "ws_clsFrom": "", "ws_clsTo": "",
    "ws_mdlclsFrom": "", "ws_mdlclsTo": "",
    "ws_smlclsFrom": "", "ws_smlclsTo": "",
})
html2 = r2.content.decode("shift_jis", errors="replace")

flg1 = re.search(r'MTRV0010040\.php([^\s"\'<\\]*ws_work_flg=1[^\s"\'<\\]*)', html2)
if not flg1:
    print("ws_work_flg=1 URLが見つかりません")
    exit(1)

trigger_url = BASE + "/MT/MTRV/MTRV0010040.php" + flg1.group(1)
print(f"\n[STEP1] トリガーGET")
print(f"  URL: {trigger_url}")
r3 = s.get(trigger_url, timeout=15)
html3 = r3.content.decode("shift_jis", errors="replace")
print(f"  status={r3.status_code}, size={len(html3)}")
print(f"  クッキー: {list(s.cookies.keys())}")

# フォームのフィールドを抽出
action  = re.search(r'action="([^"]+)"', html3, re.IGNORECASE)
j_class = re.search(r'name="ws_jClass"\s+value="([^"]+)"', html3, re.IGNORECASE)
j_args  = re.search(r'name="ws_jArgs"\s+value="([^"]+)"', html3, re.IGNORECASE)

form_action = action.group(1)
ws_jClass   = j_class.group(1)
ws_jArgs    = j_args.group(1)

print(f"\n  フォームaction: {form_action}")
print(f"  ws_jClass: {ws_jClass}")
print(f"  ws_jArgs(全体): {ws_jArgs}")

# 方法1: requestsのparamsを使う（正しいURLエンコード）
print(f"\n[STEP2-A] requests.paramsでGET")
r4a = s.get(form_action, params={"ws_jClass": ws_jClass, "ws_jArgs": ws_jArgs}, timeout=15)
print(f"  実際のURL: {r4a.url}")
print(f"  status={r4a.status_code}, size={len(r4a.content)}")
print(f"  リダイレクト履歴: {[rr.status_code for rr in r4a.history]}")
html4a = r4a.content.decode("shift_jis", errors="replace")
print(f"  レスポンス先頭: {html4a[:200]}")

# 方法2: Refererヘッダーを付けてGET
print(f"\n[STEP2-B] Refererヘッダー付きでGET")
r4b = s.get(
    form_action,
    params={"ws_jClass": ws_jClass, "ws_jArgs": ws_jArgs},
    headers={"Referer": trigger_url},
    timeout=15,
)
print(f"  status={r4b.status_code}, size={len(r4b.content)}")
html4b = r4b.content.decode("shift_jis", errors="replace")
print(f"  レスポンス先頭: {html4b[:200]}")
