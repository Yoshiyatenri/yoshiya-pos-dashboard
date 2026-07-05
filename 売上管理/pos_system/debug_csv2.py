"""新ウィンドウ（MTRV0010040）の変化を長時間観察するデバッグスクリプト"""
import json
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

cfg = json.load(open("config.json", encoding="utf-8"))

opts = Options()
opts.add_argument("--headless")
opts.add_experimental_option("prefs", {
    "download.default_directory": r"C:\one_tenri\OneDrive\HTY\vscode\pos_system\downloads",
    "download.prompt_for_download": False,
})
driver = webdriver.Edge(options=opts)

# ログイン
driver.get(cfg["login_url"])
time.sleep(2)
driver.find_element(By.NAME, "ws_userId").send_keys(cfg["user_id"])
driver.find_element(By.NAME, "ws_pswd").send_keys(cfg["password"])
driver.execute_script("document.Login.submit()")
time.sleep(3)

# CSV出力ページ
driver.get(cfg["csv_url"])
time.sleep(2)

driver.execute_script(
    "var s=document.querySelector('select[name=\"ws_streCd\"]');"
    "for(var i=0;i<s.options.length;i++)s.options[i].selected=true;"
)
for name in ("ws_dateFrom", "ws_dateTo"):
    el = driver.find_element(By.NAME, name)
    el.clear()
    el.send_keys("20260625")
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_output_flg"][value="1"]').click()
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_stre_sum_flg"][value="1"]').click()
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_outFormat"][value="1"]').click()

main_handle = driver.current_window_handle
btn = driver.find_element(By.CSS_SELECTOR, 'input[type="button"][value*="実行"]')
btn.click()
time.sleep(3)

# 新ウィンドウに切り替え
new_handles = [h for h in driver.window_handles if h != main_handle]
if new_handles:
    driver.switch_to.window(new_handles[0])
    print("新ウィンドウURL:", driver.current_url)

# 最大5分間、ページ変化・リンクを監視
for i in range(60):
    time.sleep(5)
    src = driver.page_source
    url = driver.current_url
    print(f"\n--- {(i+1)*5}秒後 ---")
    print("URL:", url)
    # リンクをすべてチェック
    for a in driver.find_elements(By.TAG_NAME, "a"):
        href = a.get_attribute("href") or ""
        if href:
            print("  リンク:", href, "|", a.text[:30])
    # input[type=button]をチェック
    for b in driver.find_elements(By.CSS_SELECTOR, "input[type='button']"):
        print("  ボタン:", b.get_attribute("value"))
    # ページ内容を一部表示
    import re
    text = re.sub(r'<[^>]+>', ' ', src)[:300]
    print("  テキスト:", text[:200])
    # URLが変わったら詳細表示
    if "download" in url.lower() or ".csv" in url.lower():
        print("*** ダウンロードURL発見! ***")
        break
    # ページにCSVリンクがあれば
    if ".csv" in src.lower():
        print("*** ページ内にCSVリンク発見! ***")
        break

print("\n最終ページソース(2000文字):")
print(driver.page_source[:2000])
driver.quit()
