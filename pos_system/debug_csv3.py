"""CSVページのJavaScript・ボタン動作・ネットワークを詳細調査"""
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

cfg = json.load(open("config.json", encoding="utf-8"))

# --- 方法1: requestsでHTTPフローを直接確認 ---
print("=== requests でHTTPフロー確認 ===")
s = requests.Session()
# ログイン
r = s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"],
    "ws_pswd": cfg["password"],
    "ws_savePswd": "1",
    "ws_actType": "1",
}, allow_redirects=True)
print("ログイン後URL:", r.url)
print("ステータス:", r.status_code)

# CSVページにPOST
store_list = ",".join(str(i) for i in [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100])
r2 = s.post(cfg["csv_url"], data={
    "ws_streCd": [str(i) for i in [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]],
    "ws_stre_list": store_list,
    "ws_dateFrom": "20260625",
    "ws_dateTo": "20260625",
    "ws_output_flg": "1",
    "ws_outFormat": "1",
    "ws_stre_sum_flg": "1",
    "ws_bussId": "6",
    "ws_Entry": "",
    "ws_clsFlg": "",
    "ws_clsFrom": "",
    "ws_clsTo": "",
    "ws_mdlclsFrom": "",
    "ws_mdlclsTo": "",
    "ws_smlclsFrom": "",
    "ws_smlclsTo": "",
}, allow_redirects=True)
print("CSV POST後URL:", r2.url)
print("ステータス:", r2.status_code)
print("Content-Type:", r2.headers.get("Content-Type",""))
print("Content-Disposition:", r2.headers.get("Content-Disposition",""))
print("レスポンスサイズ:", len(r2.content), "bytes")
if "csv" in r2.headers.get("Content-Type","").lower() or "csv" in r2.headers.get("Content-Disposition","").lower():
    print("*** CSVレスポンスが直接返ってきた! ***")
    with open("downloads/test_direct.csv", "wb") as f:
        f.write(r2.content)
else:
    print("レスポンス先頭300文字:")
    try:
        print(r2.content[:300].decode("shift_jis", errors="replace"))
    except:
        print(r2.content[:300])

# --- 方法2: SeleniumでCSVページのJSとボタンonclick属性を確認 ---
print("\n=== Selenium でページJS確認 ===")
opts = Options()
opts.add_argument("--headless")
driver = webdriver.Edge(options=opts)

driver.get(cfg["login_url"])
time.sleep(2)
driver.find_element(By.NAME, "ws_userId").send_keys(cfg["user_id"])
driver.find_element(By.NAME, "ws_pswd").send_keys(cfg["password"])
driver.execute_script("document.Login.submit()")
time.sleep(3)

driver.get(cfg["csv_url"])
time.sleep(2)

# ボタンのonclick属性
print("全ボタンのonclick:")
for btn in driver.find_elements(By.CSS_SELECTOR, "input[type='button']"):
    val = btn.get_attribute("value") or ""
    onclick = btn.get_attribute("onclick") or ""
    print(f"  [{val}] onclick={onclick}")

# スクリプトタグの内容
print("\nページ内スクリプト:")
scripts = driver.find_elements(By.TAG_NAME, "script")
for sc in scripts:
    src = sc.get_attribute("src") or ""
    inner = sc.get_attribute("innerHTML") or ""
    if inner:
        print("インラインスクリプト:", inner[:500])
    elif src:
        print("外部スクリプト:", src)

driver.quit()
