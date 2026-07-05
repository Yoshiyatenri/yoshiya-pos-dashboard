"""
エンドツーエンド診断スクリプト
- フォームページのGET → 隠しフィールド取得 → POSTジョブ送信
- ws_work_flg=1 トリガーGET
- フォーム自動送信 (onLoad) も実行
- 15分間ポーリング (1分間隔、フィルターなし)
- 途中結果をHTMLファイルに保存
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

cfg = json.load(open("config.json", encoding="utf-8"))
BASE = "https://www.netdoa-nx.jp"
STORE_CODES = [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 100]
DL_LIST_URL = f"{BASE}/DL/DL0010020.php"

Path("downloads").mkdir(exist_ok=True)
Path("debug_html").mkdir(exist_ok=True)

s = requests.Session()
s.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
})

# ─── 1. ログイン ───
print("[1] ログイン...")
r_login = s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"],
    "ws_pswd": cfg["password"],
    "ws_savePswd": "1",
    "ws_actType": "1",
})
print(f"  status={r_login.status_code}, cookies={list(s.cookies.keys())}")
if "PHPSESSID" not in s.cookies:
    print("  ERROR: ログイン失敗")
    exit(1)

# ─── 2. フォームページGET → 隠しフィールド収集 ───
form_url = cfg["csv_url"]
print(f"\n[2] フォームページGET: {form_url}")
r_form = s.get(form_url)
form_html = r_form.content.decode("shift_jis", errors="replace")
Path("debug_html/form_page.html").write_text(form_html, encoding="utf-8")
print(f"  status={r_form.status_code}, size={len(form_html)}")

# hidden フィールドを2パターンで抽出
hidden = {}
for m in re.finditer(
    r'<input[^>]+>', form_html, re.IGNORECASE
):
    tag = m.group(0)
    if 'hidden' not in tag.lower():
        continue
    name = re.search(r'name=["\']([^"\']+)["\']', tag, re.IGNORECASE)
    value = re.search(r'value=["\']([^"\']*)["\']', tag, re.IGNORECASE)
    if name:
        hidden[name.group(1)] = value.group(1) if value else ""
print(f"  隠しフィールド: {hidden}")

# ─── 3. 送信前のDLリンクを記録 ───
print("\n[3] 送信前のDLリンクを記録...")
r_before = s.get(DL_LIST_URL)
html_before = r_before.content.decode("shift_jis", errors="replace")
Path("debug_html/dl_before.html").write_text(html_before, encoding="utf-8")
before_links = re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', html_before, re.IGNORECASE)
before_ts = set()
for _, text in before_links:
    m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
    if m:
        before_ts.add(m.group(1))
print(f"  既存リンク数: {len(before_links)}, 最新: {max(before_ts) if before_ts else 'なし'}")

# ─── 4. ジョブPOST送信 ───
date_str = "20260625"
post_data = {**hidden}
post_data.update({
    "ws_streCd":      [str(i) for i in STORE_CODES],
    "ws_stre_list":   ",".join(str(i) for i in STORE_CODES),
    "ws_dateFrom":    date_str,
    "ws_dateTo":      date_str,
    "ws_output_flg":  "1",
    "ws_outFormat":   "1",
    "ws_stre_sum_flg": "1",
    "ws_bussId":      "6",
    "ws_Entry":       "実行",
    "ws_clsFlg": "", "ws_clsFrom": "", "ws_clsTo": "",
    "ws_mdlclsFrom": "", "ws_mdlclsTo": "",
    "ws_smlclsFrom": "", "ws_smlclsTo": "",
})

print(f"\n[4] ジョブPOST: {form_url}")
r_post = s.post(form_url, data=post_data)
post_html = r_post.content.decode("shift_jis", errors="replace")
Path("debug_html/post_response.html").write_text(post_html, encoding="utf-8")
print(f"  status={r_post.status_code}, size={len(post_html)}")
print(f"  → debug_html/post_response.html に保存")

submitted_at = datetime.now()
print(f"  送信時刻: {submitted_at.strftime('%H:%M:%S')}")

# MTRV0010040 の出現を確認
all_mtrv = re.findall(r'MTRV0010040[^<\s"\']{0,150}', post_html)
print(f"  MTRV0010040 出現: {all_mtrv[:3]}")

# ws_work_flg=1 URL を抽出
flg1 = re.search(r'(MTRV0010040\.php[^<"\']{0,200}ws_work_flg=1[^<"\']{0,100})', post_html)

# ─── 5. トリガーGET (ws_work_flg=1) ───
trig_html = ""
trigger_url = ""
if flg1:
    trigger_url = f"{BASE}/MT/MTRV/{flg1.group(1).strip()}"
    print(f"\n[5] トリガーGET: {trigger_url[:100]}...")
    r_trig = s.get(trigger_url, timeout=15)
    trig_html = r_trig.content.decode("shift_jis", errors="replace")
    Path("debug_html/trigger_response.html").write_text(trig_html, encoding="utf-8")
    print(f"  status={r_trig.status_code}, size={len(trig_html)}")
    print(f"  → debug_html/trigger_response.html に保存")
    print(f"  先頭200文字: {trig_html[:200]}")
else:
    print("\n[5] WARNING: ws_work_flg=1 URLが見つかりません")
    print(f"  POSTレスポンス先頭500文字:")
    print(post_html[:500])

# ─── 6. フォーム自動送信 (onLoad="document.CSV.submit()") ───
if trig_html:
    action_m  = re.search(r'action=["\']([^"\']+)["\']', trig_html, re.IGNORECASE)
    class_m   = re.search(r'name=["\']ws_jClass["\'][^>]+value=["\']([^"\']+)["\']', trig_html, re.IGNORECASE)
    args_m    = re.search(r'name=["\']ws_jArgs["\'][^>]+value=["\']([^"\']+)["\']', trig_html, re.IGNORECASE)

    if action_m and class_m and args_m:
        form_action = action_m.group(1)
        ws_jClass   = class_m.group(1)
        ws_jArgs    = args_m.group(1)
        print(f"\n[6] フォーム自動送信 (GET)...")
        print(f"  action: {form_action}")
        print(f"  ws_jClass: {ws_jClass}")
        print(f"  ws_jArgs: {ws_jArgs[:50]}...")

        r_sub = s.get(
            form_action,
            params={"ws_jClass": ws_jClass, "ws_jArgs": ws_jArgs},
            headers={"Referer": trigger_url} if trigger_url else {},
            timeout=30,
        )
        print(f"  status={r_sub.status_code}, size={len(r_sub.content)}")
        print(f"  Content-Type: {r_sub.headers.get('Content-Type','')}")
        print(f"  レスポンス先頭: {r_sub.content[:100]}")
        Path("debug_html/submit_response.html").write_text(
            r_sub.content.decode("shift_jis", errors="replace"), encoding="utf-8"
        )
    else:
        print(f"\n[6] フォームフィールドが見つかりません")
        print(f"  trig_html先頭: {trig_html[:300]}")

# ─── 7. 15分ポーリング (フィルターなし) ───
print(f"\n[7] ポーリング開始 (1分間隔 × 15回 = 15分)...")
print(f"    送信時刻: {submitted_at.strftime('%H:%M:%S')}")
print(f"    完了予想: {submitted_at.strftime('%H')}:{int(submitted_at.strftime('%M'))+10:02d}前後")

found = False
for i in range(15):
    time.sleep(60)
    elapsed = i + 1
    r_dl = s.get(DL_LIST_URL)
    dl_html = r_dl.content.decode("shift_jis", errors="replace")

    all_links = re.findall(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', dl_html, re.IGNORECASE)
    new_links = []
    for url, text in all_links:
        m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', text)
        if m and m.group(1) not in before_ts:
            new_links.append((url, text.strip(), m.group(1)))

    total = len(all_links)
    if new_links:
        print(f"\n  ★★★ {elapsed}分後: 新しいリンク {len(new_links)}件 発見! ★★★")
        for url, text, ts in new_links:
            print(f"    タイトル : {text}")
            print(f"    タイムスタンプ: {ts}")
            print(f"    URL: {url}")
            r_csv = s.get(url)
            print(f"    DLサイズ: {len(r_csv.content):,} bytes")
            if len(r_csv.content) > 100:
                safe_ts = ts.replace("/", "-").replace(" ", "_").replace(":", "-")
                fname = f"downloads/e2e_{safe_ts}.csv"
                Path(fname).write_bytes(r_csv.content)
                print(f"    保存: {fname}")
        found = True
        break
    else:
        print(f"  {elapsed:2d}分経過... リンク総数={total} (新規なし)")

if not found:
    print("\n15分経過しても新しいリンクが見つかりませんでした")
    # 最後のDLページHTMLを保存
    Path("debug_html/dl_after.html").write_text(dl_html, encoding="utf-8")
    print("→ debug_html/dl_after.html に最終状態を保存")
    print("\n現在のリンク一覧 (全件):")
    for url, text in all_links:
        print(f"  {text.strip()[:80]}")

print("\n完了")
