"""IMAP接続確認・件名一覧表示用のデバッグスクリプト（本番では使わない）。"""
from mail_check import load_config, connect_imap, fetch_all_uids, fetch_header


def main():
    config = load_config()
    print(f"接続先: {config['imap_host']}:{config['imap_port']}")

    conn = connect_imap(config)
    print("ログイン成功。INBOXを選択しました。")

    try:
        uids = fetch_all_uids(conn)
        print(f"メール件数: {len(uids)}")

        for uid in uids[-10:]:
            header = fetch_header(conn, uid)
            print(f"UID={uid.decode()} 件名={header['subject']} 差出人={header['from']}")
    finally:
        conn.logout()


if __name__ == "__main__":
    main()
