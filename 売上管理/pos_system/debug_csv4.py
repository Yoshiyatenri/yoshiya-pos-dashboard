"""GotoEntryBtn関数の中身と実際のHTTPリクエストを確認"""
import json
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

cfg = json.load(open("config.json", encoding="utf-8"))

opts = Options()
opts.add_argument("--headless")
# パフォーマンスログを有効化してネットワークリクエストを取得
opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Edge(options=opts)

driver.get(cfg["login_url"])
time.sleep(2)
driver.find_element(By.NAME, "ws_userId").send_keys(cfg["user_id"])
driver.find_element(By.NAME, "ws_pswd").send_keys(cfg["password"])
driver.execute_script("document.Login.submit()")
time.sleep(3)

driver.get(cfg["csv_url"])
time.sleep(2)

# GotoEntryBtn関数の内容を取得
result = driver.execute_script("return typeof GotoEntryBtn !== 'undefined' ? GotoEntryBtn.toString() : 'NOT FOUND'")
print("=== GotoEntryBtn 関数 ===")
print(result)

# 外部JSファイルを取得
result2 = driver.execute_script("return typeof fc_stre_all_on !== 'undefined' ? fc_stre_all_on.toString() : 'NOT FOUND'")
print("\n=== fc_stre_all_on 関数 ===")
print(result2[:500])

# 全グローバル関数一覧
funcs = driver.execute_script("""
    return Object.keys(window).filter(k => typeof window[k] === 'function'
        && !['alert','confirm','prompt','open','close','focus'].includes(k)
        && k.startsWith('G') || k.startsWith('fc') || k.startsWith('Goto')
    ).slice(0,30)
""")
print("\n=== 関連する関数一覧 ===")
print(funcs)

driver.quit()
