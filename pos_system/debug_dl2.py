import json, re, requests

cfg = json.load(open("config.json", encoding="utf-8"))
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"
s.post(cfg["login_url"], data={
    "ws_userId": cfg["user_id"], "ws_pswd": cfg["password"],
    "ws_savePswd": "1", "ws_actType": "1",
})

# iframeのsrcを取得
r = s.get("https://www.netdoa-nx.jp/DL/DL0010010.php?ws_bussId=10")
html = r.content.decode("shift_jis", errors="replace")
iframe = re.search(r'IFRAME[^>]+SRC=["\'](\./DL0010020[^"\']*)', html, re.IGNORECASE)
src = iframe.group(1) if iframe else "./DL0010020.php"
print("IFRAME SRC:", src)

# DL0010020を取得
r2 = s.get("https://www.netdoa-nx.jp/DL/" + src.lstrip("./"))
html2 = r2.content.decode("shift_jis", errors="replace")
print("DL0010020 サイズ:", len(r2.content))
print(html2[:4000])
