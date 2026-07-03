# Netdoa NX ログイン診断

よしやPOSシステムの Netdoa NX ログイン状態を確認・診断するタスク。

## システム情報
- ログインURL: `config.json["login_url"]`（`https://www.netdoa-nx.jp/0010010.php`）
- 認証情報: `config.json` の `user_id` / `password`
- セッション確認: `PHPSESSID` が Cookie に入っていればログイン成功

## 確認手順

1. `pos_system/config.json` が存在するか確認する
2. 以下のスクリプトをスクラッチで実行してログイン状態を確認する：

```python
import json, requests
from pathlib import Path

cfg = json.loads(Path("pos_system/config.json").read_text(encoding="utf-8"))
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
r = s.post(cfg["login_url"], data={
    "ws_userId":   cfg["user_id"],
    "ws_pswd":     cfg["password"],
    "ws_savePswd": "1",
    "ws_actType":  "1",
})
ok = r.status_code == 200 and "PHPSESSID" in s.cookies
print(f"ログイン {'成功' if ok else '失敗'}")
print(f"ステータス: {r.status_code}")
print(f"Cookie: {dict(s.cookies)}")
```

## よくあるエラーと対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `PHPSESSID` が Cookie にない | ID/パスワード間違い | `config.json` を確認 |
| `status_code != 200` | ネットワーク接続なし | VPN・インターネット接続を確認 |
| `ConnectionError` | サーバーに到達できない | Netdoa NXのメンテ時間でないか確認 |
| ログイン成功なのにCSV送信失敗 | セッション切れ | download.py を最初から実行し直す |

## 関連ファイル
- `pos_system/download.py` の `login()` 関数（56行目付近）
- `pos_system/config.json`（認証情報）

ユーザーの質問や状況に応じて、上記スクリプトを実行するか、`download.py` の `login()` 関数を確認して問題を特定すること。
