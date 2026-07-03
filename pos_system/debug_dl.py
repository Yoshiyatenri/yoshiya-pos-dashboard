"""DL0010010.phpのリンク構造を確認"""
import json
import re
import requests

cfg = json.load(open("config.json", encoding="utf-8"))

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})

r = s.get("https://www.netdoa-nx.jp/DL/DL0010010.php?ws_bussId=10")
html = r.content.decode("shift_jis", errors="replace")

print("ステータス:", r.status_code)
print("サイズ:", len(r.content))

# リンクを全部抽出
links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE)
print("\n=== リンク一覧 ===")
for href, text in links:
    print(f"  [{text.strip()}] → {href}")

print("\n=== HTML全文 ===")
print(html[:5000])
