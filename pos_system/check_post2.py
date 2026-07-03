"""
GETでフォームページを取得してから、隠しフィールドを含めてPOSTする
"""
import json, re
from datetime import datetime, timedelta
from pathlib import Path
import requests
from html.parser import HTMLParser

cfg = json.load(open("config.json", encoding="utf-8"))
BASE_URL = "https://www.netdoa-nx.jp"

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})
print("ログイン完了")

# Step1: フォームページをGET
print(f"\n[Step1] フォームGET: {cfg['csv_url']}")
r_get = s.get(cfg["csv_url"])
html_get = r_get.content.decode("shift_jis", errors="replace")
Path("debug_html").mkdir(exist_ok=True)
Path("debug_html/form_get2.html").write_text(html_get, encoding="utf-8")
print(f"  サイズ={len(html_get)}文字")

# フォームのaction URLを取得
action_m = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html_get, re.I)
form_action = action_m.group(1) if action_m else cfg["csv_url"]
if form_action.startswith("/"):
    form_action = BASE_URL + form_action
print(f"  フォームaction: {form_action}")

# hidden フィールドを全部取得
hidden_fields = {}
for m in re.finditer(r'<input[^>]+type=["\']?hidden["\']?[^>]*>', html_get, re.I):
    tag = m.group(0)
    name_m  = re.search(r'name=["\']([^"\']+)["\']', tag, re.I)
    value_m = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
    if name_m:
        hidden_fields[name_m.group(1)] = value_m.group(1) if value_m else ""

print(f"  hidden フィールド({len(hidden_fields)}件):")
for k, v in hidden_fields.items():
    print(f"    {k} = {v[:50]}")

# select[name=ws_streCd] の option 値も確認
streCd_options = re.findall(
    r'<option[^>]+value=["\']?(\d+)["\']?[^>]*>',
    html_get, re.I
)
print(f"  ws_streCd optionの数: {len(streCd_options)}件 -> {streCd_options[:5]}...")

# Step2: POST
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
store_list = ",".join(str(i) for i in STORE_CODES)

# hiddenフィールドをベースにして、送信値で上書き
post_data = dict(hidden_fields)
post_data.update({
    "ws_bussId":      "6",
    "ws_stre_list":   store_list,
    "ws_streCd":      [str(i) for i in STORE_CODES],
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
    "ws_Entry":       "実行",
})

print(f"\n[Step2] POST送信: {form_action}")
r_post = s.post(form_action, data=post_data)
html_post = r_post.content.decode("shift_jis", errors="replace")
Path("debug_html/post_response2.html").write_text(html_post, encoding="utf-8")
print(f"  ステータス: {r_post.status_code} / サイズ: {len(html_post)}文字")

for kw in ["MTRV0010040", "ws_work_flg=1", "window.open", "エラー", "ws_jClass"]:
    print(f"  {'✓' if kw in html_post else '✗'} {kw}")

# エラーメッセージをHTMLから抽出（タグを除いてテキストのみ）
text_post = re.sub(r'<script[^>]*>.*?</script>', '', html_post, flags=re.DOTALL|re.I)
text_post = re.sub(r'<[^>]+>', ' ', text_post)
text_post = re.sub(r'\s+', ' ', text_post).strip()

# スクリプト除いた後のテキストで本物のエラーを探す
real_errors = [line for line in text_post.split(' ') if 'エラー' in line and len(line) < 50]
if real_errors:
    print(f"\n  実際のエラーメッセージ候補: {real_errors[:5]}")

print(f"\nページテキスト(先頭800文字、スクリプト除外):\n{text_post[:800]}")

# ws_work_flg=1 URLを抽出
triggers = re.findall(r'MTRV0010040\.php[^\s"\'<\\]*', html_post)
if triggers:
    print(f"\n★ トリガーURL発見: {triggers[0][:120]}")
else:
    print(f"\n✗ トリガーURL見つからず")
