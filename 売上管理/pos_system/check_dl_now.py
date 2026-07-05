"""DLページの現在の全リンクを確認 (フィルターなし)"""
import json, re, requests
from datetime import datetime

cfg = json.load(open("config.json", encoding="utf-8"))
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})

r = s.get("https://www.netdoa-nx.jp/DL/DL0010020.php")
html = r.content.decode("shift_jis", errors="replace")

print(f"確認時刻: {datetime.now().strftime('%H:%M:%S')}")
print(f"レスポンスサイズ: {len(html)} bytes\n")

# 全リンク取得
blocks = re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', html, re.IGNORECASE)
print(f"=== 全リンク ({len(blocks)}件) ===")
for url, text in blocks:
    text = text.strip()
    print(f"  [{text}]")
    m = re.search(r'\[(\d{{4}}/\d{{2}}/\d{{2}} \d{{2}}:\d{{2}}:\d{{2}})\]', text)
    if m:
        print(f"    → 作成時刻: {m.group(1)}")
    print(f"    → URL: {url[:70]}...")

# 今日(2026-06-26)のリンクだけ抽出
print(f"\n=== 今日(2026-06-26)のリンク ===")
today_links = []
for url, text in blocks:
    if "2026/06/26" in text:
        text = text.strip()
        m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
        ts = m.group(1) if m else "不明"
        today_links.append((ts, text, url))
        print(f"  [{text}]  → {url[:60]}...")

if not today_links:
    print("  今日のリンクなし")
else:
    # 最新リンクをダウンロード
    latest = sorted(today_links, reverse=True)[0]
    print(f"\n最新リンク: {latest[0]} - {latest[1][:40]}")
    print(f"ダウンロード試行...")
    r2 = s.get(latest[2])
    print(f"  size={len(r2.content)} bytes, Content-Type={r2.headers.get('Content-Type','')}")
    if len(r2.content) > 100:
        fname = f"downloads/check_{latest[0].replace('/','-').replace(' ','_').replace(':','-')}.csv"
        open(fname, "wb").write(r2.content)
        print(f"  保存: {fname}")
        # 先頭を表示
        head = r2.content[:200].decode("shift_jis", errors="replace")
        print(f"  先頭: {head}")
