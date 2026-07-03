"""
DLページを監視して新しいリンクが出たら自動ダウンロード
使い方: python monitor_dl.py
Ctrl+C で停止
"""
import json, re, time, sys
from datetime import datetime
from pathlib import Path
import requests

cfg = json.load(open("config.json", encoding="utf-8"))
DL_LIST_URL = "https://www.netdoa-nx.jp/DL/DL0010020.php"
POLL_SEC = 30
MAX_WAIT_MIN = 30

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print(f"ログイン完了 ({datetime.now().strftime('%H:%M:%S')})")

def get_links():
    r = s.get(DL_LIST_URL)
    html = r.content.decode("shift_jis", errors="replace")
    blocks = re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', html, re.IGNORECASE)
    result = {}
    for url, text in blocks:
        m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
        if m:
            result[m.group(1)] = (url, text.strip())
    return result

# 現在のリンクを記録
before = get_links()
print(f"現在のリンク数: {len(before)}件")
if before:
    latest_ts = max(before.keys())
    print(f"最新タイムスタンプ: {latest_ts}")
print(f"\n--- 手動でジョブを実行してください ---")
print(f"監視中... ({POLL_SEC}秒ごとに確認, 最大{MAX_WAIT_MIN}分)\n")

Path("downloads").mkdir(exist_ok=True)
polls = MAX_WAIT_MIN * 60 // POLL_SEC

for i in range(polls):
    time.sleep(POLL_SEC)
    now_str = datetime.now().strftime('%H:%M:%S')
    try:
        current = get_links()
    except Exception as e:
        print(f"[{now_str}] エラー: {e}")
        continue

    new_ts = set(current.keys()) - set(before.keys())
    if new_ts:
        print(f"\n★★★ [{now_str}] 新しいリンク {len(new_ts)}件 発見! ★★★")
        for ts in sorted(new_ts):
            url, text = current[ts]
            print(f"  タイトル : {text}")
            print(f"  タイムスタンプ: {ts}")
            print(f"  URL: {url}")
            r2 = s.get(url)
            print(f"  DLサイズ: {len(r2.content):,} bytes")
            if len(r2.content) > 100:
                safe = ts.replace("/","-").replace(" ","_").replace(":","-")
                fname = Path("downloads") / f"{safe}.csv"
                fname.write_bytes(r2.content)
                print(f"  → 保存: {fname}")
                head = r2.content[:300].decode("shift_jis", errors="replace")
                print(f"  先頭:\n{head}")
        sys.exit(0)
    else:
        elapsed = (i + 1) * POLL_SEC
        print(f"[{now_str}] {elapsed//60}分{elapsed%60:02d}秒経過... リンク数={len(current)} (変化なし)")

print(f"\n{MAX_WAIT_MIN}分経過しても新しいリンクが見つかりませんでした")
