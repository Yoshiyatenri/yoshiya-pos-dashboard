"""POSTレスポンスの内容を確認する"""
import json, re
from datetime import datetime, timedelta
from pathlib import Path
import requests

cfg = json.load(open("config.json", encoding="utf-8"))
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print("ログイン完了")

yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
store_list = ",".join(str(i) for i in STORE_CODES)

print(f"POST送信中 (日付={yesterday})...")
r = s.post(cfg["csv_url"], data={
    "ws_bussId":      "6",
    "ws_stre_list":   store_list,
    "ws_clsFlg":      "3",
    "ws_clsFrom":     "1",
    "ws_clsTo":       "999999",
    "ws_clsNameFrom": "",
    "ws_clsNameTo":   "",
    "ws_mdlclsFrom":  "1",
    "ws_mdlclsTo":    "999999",
    "ws_smlclsFrom":  "",
    "ws_smlclsTo":    "",
    "ws_dateFrom":    yesterday,
    "ws_dateTo":      yesterday,
    "ws_output_flg":  "1",
    "ws_outFormat":   "1",
    "ws_stre_sum_flg":"1",
})
html = r.content.decode("shift_jis", errors="replace")

Path("debug_html").mkdir(exist_ok=True)
Path("debug_html/post_response.html").write_text(html, encoding="utf-8")
print(f"レスポンス保存: debug_html/post_response.html")
print(f"ステータス: {r.status_code} / サイズ: {len(html)}文字")
print()

# キーワード確認
for kw in ["MTRV0010040", "ws_work_flg=1", "エラー", "error", "警告", "ws_jClass", "window.open"]:
    print(f"  {'✓' if kw in html else '✗'} {kw}")

# エラーメッセージ抽出
errors = re.findall(r'(?:エラー|警告|error)[^<]{0,100}', html, re.IGNORECASE)
if errors:
    print(f"\nエラー内容:")
    for e in errors[:5]:
        print(f"  {e.strip()}")

# レスポンス先頭500文字（テキストのみ）
text = re.sub(r'<[^>]+>', ' ', html)
text = re.sub(r'\s+', ' ', text).strip()
print(f"\nページテキスト (先頭500文字):\n{text[:500]}")
