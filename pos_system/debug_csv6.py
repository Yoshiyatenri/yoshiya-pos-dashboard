"""MTRV0010040?ws_work_flg=1 をrequestsで直接取得してCSVか確認"""
import json
import re
import requests

cfg = json.load(open("config.json", encoding="utf-8"))
BASE = "https://www.netdoa-nx.jp"

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# ログイン
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"],
    "ws_pswd": cfg["password"],
    "ws_savePswd": "1",
    "ws_actType": "1",
})

# CSVをPOST (ws_Entry=実行)
store_codes = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
r2 = s.post(cfg["csv_url"], data={
    "ws_streCd": [str(i) for i in store_codes],
    "ws_stre_list": ",".join(str(i) for i in store_codes),
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
})

html = r2.content.decode("shift_jis", errors="replace")

# MTRV0010040 のURLをすべて抽出
all_urls = re.findall(r'MTRV0010040[^\s"\'<\\]*', html)
print("=== MTRV0010040 URL一覧 ===")
for u in set(all_urls):
    print(u)

# ws_work_flg=1 のURLを取得
flg1_urls = [u for u in set(all_urls) if "ws_work_flg=1" in u]
if flg1_urls:
    target_url = BASE + "/MT/MTRV/" + flg1_urls[0]
    print(f"\n対象URL: {target_url}")

    r3 = s.get(target_url)
    print("ステータス:", r3.status_code)
    print("Content-Type:", r3.headers.get("Content-Type",""))
    print("Content-Disposition:", r3.headers.get("Content-Disposition",""))
    print("サイズ:", len(r3.content), "bytes")

    content_type = r3.headers.get("Content-Type","")
    disposition = r3.headers.get("Content-Disposition","")

    if "csv" in content_type.lower() or "csv" in disposition.lower() or "octet" in content_type.lower():
        print("*** CSVファイルが返ってきた! ***")
        with open("downloads/test_direct.csv", "wb") as f:
            f.write(r3.content)
        print("保存完了: downloads/test_direct.csv")
    else:
        h = r3.content.decode("shift_jis", errors="replace")
        print("\nHTML先頭500文字:")
        print(h[:500])

        # このページ内にもダウンロードURLがあるか？
        sub_urls = re.findall(r'https?://[^\s"\'<>]+', h)
        print("\nURL一覧:", sub_urls[:10])

        # CsvNameを探す
        csv_names = re.findall(r'ws_CsvName=([^&\s"\']+)', h)
        print("ws_CsvName:", csv_names)
else:
    print("ws_work_flg=1 のURLが見つかりませんでした")
    print("全URL:", set(all_urls))
