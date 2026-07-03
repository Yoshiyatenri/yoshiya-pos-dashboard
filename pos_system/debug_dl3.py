"""DL0010020.phpの現在のリンク一覧と正規表現の動作を確認"""
import json, re, requests
from datetime import datetime

cfg = json.load(open("config.json", encoding="utf-8"))
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})

r = s.get("https://www.netdoa-nx.jp/DL/DL0010020.php")
html = r.content.decode("shift_jis", errors="replace")

print("=== DL0010020.php のdownload.phpリンク全件 ===")
# HREFからdownload.phpリンクをすべて取得
all_links = re.findall(r'HREF="(https://www\.netdoa-nx\.jp/download\.php[^"]+)"', html, re.IGNORECASE)
print(f"download.phpリンク数: {len(all_links)}")

# リンクテキストも含めて取得
blocks = re.findall(r'<A HREF="(https://www\.netdoa-nx\.jp/download\.php[^"]+)"[^>]*>([^<]+)</A>', html, re.IGNORECASE)
print(f"\n=== リンクテキスト付き ({len(blocks)}件) ===")
for url, text in blocks:
    print(f"  テキスト: [{text.strip()}]")
    # 作成時間を抽出
    m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
    if m:
        created = datetime.strptime(m.group(1), "%Y/%m/%d %H:%M:%S")
        print(f"  作成時刻: {created}")
    print(f"  URL先頭: {url[:80]}...")
    print()

# 17:22以降のリンクを探す
cutoff = datetime(2026, 6, 26, 17, 21, 44)
print(f"\n=== {cutoff.strftime('%H:%M:%S')}以降のリンク ===")
for url, text in blocks:
    m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
    if m:
        created = datetime.strptime(m.group(1), "%Y/%m/%d %H:%M:%S")
        if created >= cutoff:
            print(f"  ★ {text.strip()} → {url[:60]}...")
