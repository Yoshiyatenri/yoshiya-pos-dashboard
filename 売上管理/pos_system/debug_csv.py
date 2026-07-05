"""実行後のページ動作を調べるデバッグスクリプト"""
import json
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

cfg = json.load(open("config.json", encoding="utf-8"))

opts = Options()
opts.add_argument("--headless")
driver = webdriver.Edge(options=opts)

# ログイン
driver.get(cfg["login_url"])
time.sleep(2)
driver.find_element(By.NAME, "ws_userId").send_keys(cfg["user_id"])
driver.find_element(By.NAME, "ws_pswd").send_keys(cfg["password"])
driver.execute_script("document.Login.submit()")
time.sleep(3)
print("ログイン後URL:", driver.current_url)

# CSV出力ページ
driver.get(cfg["csv_url"])
time.sleep(2)

# 全店舗選択
driver.execute_script(
    "var s=document.querySelector('select[name=\"ws_streCd\"]');"
    "for(var i=0;i<s.options.length;i++)s.options[i].selected=true;"
)

# 日付設定
for name in ("ws_dateFrom", "ws_dateTo"):
    el = driver.find_element(By.NAME, name)
    el.clear()
    el.send_keys("20260625")

# ラジオ設定
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_output_flg"][value="1"]').click()
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_stre_sum_flg"][value="1"]').click()
driver.find_element(By.CSS_SELECTOR, 'input[name="ws_outFormat"][value="1"]').click()

# 実行ボタン
btn = driver.find_element(By.CSS_SELECTOR, 'input[type="button"][value*="実行"]')
print("ボタン発見:", repr(btn.get_attribute("value")))

# ウィンドウ数を記録
handles_before = set(driver.window_handles)
btn.click()

# 少し待ってページ変化を観察
for i in range(10):
    time.sleep(2)
    print(f"--- {(i+1)*2}秒後 ---")
    print("  URL:", driver.current_url)
    print("  ウィンドウ数:", len(driver.window_handles))
    new_handles = set(driver.window_handles) - handles_before
    if new_handles:
        print("  新しいウィンドウ:", new_handles)
        driver.switch_to.window(list(new_handles)[0])
        print("  新ウィンドウURL:", driver.current_url)
    # リンクをチェック
    links = driver.find_elements(By.TAG_NAME, "a")
    for lnk in links:
        href = lnk.get_attribute("href") or ""
        if ".csv" in href.lower() or "download" in href.lower():
            print("  ダウンロードリンク発見:", href)

print("\nページソース(最初1500文字):")
print(driver.page_source[:1500])

driver.quit()
