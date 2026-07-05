"""requestsで正しいPOSTを送り、レスポンスHTML内のwindow.openを探す"""
import json
import re
import requests

cfg = json.load(open("config.json", encoding="utf-8"))
BASE = "https://www.netdoa-nx.jp"

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ログイン
r = s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"],
    "ws_pswd": cfg["password"],
    "ws_savePswd": "1",
    "ws_actType": "1",
})
print("ログイン後URL:", r.url)
print("ログインCookies:", dict(s.cookies))

# CSVページを先にGET（フォームの初期値を取得）
r_get = s.get(cfg["csv_url"])
print("\nGET CSVページ ステータス:", r_get.status_code)

# 全店舗コード
store_codes = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
store_list = ",".join(str(i) for i in store_codes)

# ws_Entry="実行" を含めてPOST
r2 = s.post(cfg["csv_url"], data={
    "ws_streCd": [str(i) for i in store_codes],
    "ws_stre_list": store_list,
    "ws_dateFrom": "20260625",
    "ws_dateTo": "20260625",
    "ws_output_flg": "1",
    "ws_outFormat": "1",
    "ws_stre_sum_flg": "1",
    "ws_bussId": "6",
    "ws_Entry": "実行",
    "ws_clsFlg": "",
    "ws_clsFrom": "",
    "ws_clsTo": "",
    "ws_mdlclsFrom": "",
    "ws_mdlclsTo": "",
    "ws_smlclsFrom": "",
    "ws_smlclsTo": "",
}, allow_redirects=True)

print("\nPOST後URL:", r2.url)
print("ステータス:", r2.status_code)
print("Content-Type:", r2.headers.get("Content-Type",""))
print("Content-Disposition:", r2.headers.get("Content-Disposition",""))
print("レスポンスサイズ:", len(r2.content), "bytes")

# HTMLとしてデコード
html = r2.content.decode("shift_jis", errors="replace")

# window.open() を探す
opens = re.findall(r'window\.open\([^)]+\)', html)
print("\n=== window.open() 呼び出し ===")
for o in opens:
    print(o)

# location.href や location.replace を探す
locations = re.findall(r'location[^;]{0,100}', html)
print("\n=== location操作 ===")
for l in locations[:10]:
    print(l)

# アンカーリンクを探す
anchors = re.findall(r'<a[^>]+href=["\'][^"\']+["\'][^>]*>[^<]*</a>', html, re.IGNORECASE)
print(f"\n=== アンカーリンク ({len(anchors)}件) ===")
for a in anchors[:20]:
    print(a)

# CSVダウンロード関連URLを探す
csv_urls = re.findall(r'https?://[^\s"\'<>]+\.csv[^\s"\'<>]*', html, re.IGNORECASE)
csv_urls2 = re.findall(r'/[^\s"\'<>]*download[^\s"\'<>]*', html, re.IGNORECASE)
print("\n=== CSV/ダウンロードURL ===")
for u in csv_urls + csv_urls2:
    print(u)

# MTRV0010040 URL を探す（ポップアップURL）
popup_urls = re.findall(r'MTRV0010040[^"\'<\s]*', html)
print("\n=== MTRV0010040 URL ===")
for u in popup_urls:
    print(u)

print("\n=== HTML先頭2000文字 ===")
print(html[:2000])
