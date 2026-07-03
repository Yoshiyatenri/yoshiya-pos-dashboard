"""
フォームページのHTML・送受信内容を確認する診断スクリプト
実行: python check_form.py
"""
import json, re, sys
from pathlib import Path
import requests

cfg = json.load(open("config.json", encoding="utf-8"))
BASE_URL = "https://www.netdoa-nx.jp"

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 1. ログイン
r = s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print(f"[1] ログイン: status={r.status_code}, PHPSESSID={'あり' if 'PHPSESSID' in s.cookies else 'なし'}")

# 2. フォームページを GET して全フィールドを表示
print(f"\n[2] フォームページを取得中: {cfg['csv_url']}")
r2 = s.get(cfg["csv_url"])
html = r2.content.decode("shift_jis", errors="replace")
print(f"    status={r2.status_code}, サイズ={len(html)}文字")

# HTMLを保存
Path("debug_html").mkdir(exist_ok=True)
Path("debug_html/form_get.html").write_text(html, encoding="utf-8")
print(f"    → debug_html/form_get.html に保存しました")

# 3. input/select タグをすべて表示
print("\n[3] フォームフィールド一覧:")
print("-" * 60)

# input フィールド
inputs = re.findall(r'<input[^>]+>', html, re.IGNORECASE)
for tag in inputs:
    name  = re.search(r'name=["\']?([^\s"\'>/]+)', tag, re.I)
    val   = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
    type_ = re.search(r'type=["\']?([^\s"\'>/]+)', tag, re.I)
    n = name.group(1) if name else "(name不明)"
    v = val.group(1) if val else ""
    t = type_.group(1) if type_ else "text"
    print(f"  input [{t:10s}] name={n:25s} value={v}")

# select フィールド
selects = re.findall(r'<select[^>]+>.*?</select>', html, re.IGNORECASE | re.DOTALL)
for sel in selects:
    name = re.search(r'name=["\']?([^\s"\'>/]+)', sel, re.I)
    options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>', sel, re.I | re.DOTALL)
    n = name.group(1) if name else "(name不明)"
    selected = [(v, t.strip()) for v, t in options if 'selected' in sel.lower()]
    print(f"  select name={n}")
    for v, t in options[:5]:
        mark = " ← デフォルト" if any(sv == v for sv, _ in selected) else ""
        print(f"         option value='{v}' text='{t[:20]}'{mark}")
    if len(options) > 5:
        print(f"         ...他{len(options)-5}件")

# 4. 日付フィールドの値を特に確認
print("\n[4] 日付フィールド確認:")
date_fields = re.findall(r'<input[^>]+(?:date|Date|from|From|to|To)[^>]*>', html, re.I)
for tag in date_fields:
    print(f"  {tag[:150]}")

# 5. ws_dateFrom の実際の形式を探す
date_pattern = re.findall(r'value=["\'](\d{4}[-/]\d{2}[-/]\d{2}|\d{8})["\']', html, re.I)
if date_pattern:
    print(f"\n[5] 日付形式の候補: {date_pattern}")
else:
    print(f"\n[5] 日付形式: HTMLに日付値が見つかりませんでした（空フィールド or JS で設定）")

# 6. 実際にPOSTしてレスポンスを確認（実行はしない、ドライラン）
from datetime import datetime, timedelta
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
print(f"\n[6] テスト送信（前日={yesterday}）...")

STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
store_list = ",".join(str(i) for i in STORE_CODES)

r3 = s.post(cfg["csv_url"], data={
    "ws_streCd":      [str(i) for i in STORE_CODES],
    "ws_stre_list":   store_list,
    "ws_dateFrom":    yesterday,
    "ws_dateTo":      yesterday,
    "ws_output_flg":  "1",
    "ws_outFormat":   "1",
    "ws_stre_sum_flg":"1",
    "ws_bussId":      "6",
    "ws_Entry":       "実行",
    "ws_clsFlg": "", "ws_clsFrom": "", "ws_clsTo": "",
    "ws_mdlclsFrom": "", "ws_mdlclsTo": "",
    "ws_smlclsFrom": "", "ws_smlclsTo": "",
})
html3 = r3.content.decode("shift_jis", errors="replace")
Path("debug_html/form_post_response.html").write_text(html3, encoding="utf-8")
print(f"    POST status={r3.status_code}, サイズ={len(html3)}文字")
print(f"    → debug_html/form_post_response.html に保存")

# 重要なキーワードを確認
keywords = ["MTRV0010040", "ws_work_flg=1", "エラー", "error", "ws_jClass", "ws_jArgs", "警告", "失敗"]
print(f"\n[7] レスポンス内のキーワード:")
for kw in keywords:
    found = kw in html3
    print(f"  {'✓' if found else '✗'} {kw}")

# エラーメッセージがあれば表示
err = re.findall(r'<[^>]*(?:error|エラー|警告)[^>]*>([^<]+)<', html3, re.I)
if err:
    print(f"\n[8] エラーメッセージ: {err}")

# trigger URL を抽出
trigger = re.findall(r'MTRV0010040\.php[^\s"\'<\\]*ws_work_flg=1[^\s"\'<\\]*', html3)
print(f"\n[8] トリガーURL: {'発見: ' + trigger[0][:80] if trigger else '見つかりませんでした ← 問題の可能性あり'}")

print("\n完了。debug_html/ フォルダのHTMLファイルを確認してください。")
