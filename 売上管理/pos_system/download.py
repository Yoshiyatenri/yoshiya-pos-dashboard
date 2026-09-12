"""
Netdoa NX から前日の商品売上実績CSVを自動ダウンロードするスクリプト
処理フロー:
  1. ログイン
  2. CSV生成ジョブをPOST送信
  3. DL0010020.php を定期確認し、新しいリンクが出たらダウンロード
"""
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"download_{datetime.now():%Y%m}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

BASE_URL         = "https://www.netdoa-nx.jp"
DL_LIST_URL      = f"{BASE_URL}/DL/DL0010020.php"
VISITORS_JOB_URL = f"{BASE_URL}/SA/SAR6/SAR60010010.php"
STORE_CODES = [1,2,3,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,100]
POLL_INTERVAL_SEC = 15    # 15秒ごとに確認
MAX_WAIT_MIN      = 25    # 最大25分待機


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def login(session: requests.Session, cfg: dict) -> bool:
    r = session.post(cfg["login_url"], data={
        "ws_userId":   cfg["user_id"],
        "ws_pswd":     cfg["password"],
        "ws_savePswd": "1",
        "ws_actType":  "1",
    })
    ok = r.status_code == 200 and "PHPSESSID" in session.cookies
    log.info(f"ログイン {'成功' if ok else '失敗'}")
    return ok


def submit_csv_job(session: requests.Session, cfg: dict, date_str: str) -> bool:
    """CSV生成ジョブをサーバーに送信し、ブラウザのonLoadチェーンを再現してCSV生成をトリガーする"""
    # サーバー側のセッション初期化のため、POSTの前にGETが必要
    session.get(cfg["csv_url"])

    store_list = ",".join(str(i) for i in STORE_CODES)
    r = session.post(cfg["csv_url"], data={
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
        "ws_dateFrom":    date_str,
        "ws_dateTo":      date_str,
        "ws_output_flg":  "1",
        "ws_outFormat":   "1",
        "ws_stre_sum_flg":"1",
        "ws_Entry":       "実行",
    })
    html = r.content.decode("shift_jis", errors="replace")

    if "MTRV0010040" not in html:
        log.error(f"ジョブ送信失敗 (ステータス={r.status_code})")
        return False

    log.info("ジョブ送信成功（MTRV0010040検出）")

    # ブラウザの onLoad="document.CSV.submit()" チェーンを再現
    # step1: openCsvWin URL (ws_work_flg=1) をGET
    m = re.search(r"openCsvWin\('([^']+)'", html)
    if not m:
        log.warning("openCsvWin URLなし。チェーン省略")
        return True

    url1 = BASE_URL + m.group(1)
    log.info("トリガーチェーン step1 (ws_work_flg=1)...")
    r1 = session.get(url1)
    html1 = r1.content.decode("shift_jis", errors="replace")

    # step2: レスポンスのフォーム（ws_work_flg=2）をGET → 実際のCSV生成がここで開始される
    if 'document.CSV.submit()' not in html1:
        log.warning("step1にonLoadフォームなし。チェーン省略")
        return True

    params = {}
    for inp in re.finditer(r'<INPUT[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html1, re.IGNORECASE):
        params[inp.group(1)] = inp.group(2)
    action_m = re.search(r'<FORM[^>]+action=["\']([^"\']+)["\']', html1, re.IGNORECASE)
    action = action_m.group(1) if action_m else f"{BASE_URL}/MT/MTRV/MTRV0010040.php"
    if not action.startswith("http"):
        action = BASE_URL + action

    log.info(f"トリガーチェーン step2 (ws_work_flg={params.get('ws_work_flg', '?')})...")
    r2 = session.get(action, params=params)
    html2 = r2.content.decode("shift_jis", errors="replace")
    text2 = re.sub(r'<[^>]+>', ' ', html2)
    text2 = re.sub(r'\s+', ' ', text2).strip()
    log.info(f"step2レスポンス: {text2[:80]}")

    ok = r.status_code == 200
    log.info(f"ジョブ送信 {'成功' if ok else '失敗'}")
    return ok


def get_dl_links(session: requests.Session) -> list[dict]:
    """DL0010020.phpからダウンロードリンク一覧を取得する"""
    r = session.get(DL_LIST_URL)
    html = r.content.decode("shift_jis", errors="replace")

    # リンクと作成時刻を抽出
    # パターン: href="https://...download.php?..." テキスト内に [YYYY/MM/DD HH:MM:SS]
    pattern = re.compile(
        r'<A HREF="(https://www\.netdoa-nx\.jp/download\.php\?[^"]+)"[^>]*>([^<]+)</A>',
        re.IGNORECASE,
    )
    links = []
    for m in pattern.finditer(html):
        url, full_text = m.group(1), m.group(2)
        ts_m = re.search(r'\[(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\]', full_text)
        if not ts_m:
            continue
        created_at = datetime.strptime(ts_m.group(1), "%Y/%m/%d %H:%M:%S")
        title = full_text[:ts_m.start()].strip()
        links.append({"url": url, "title": title, "created_at": created_at})
    return links


def poll_and_download(session: requests.Session, submitted_at: datetime, out_path: Path, date_str: str = "") -> bool:
    """ジョブ送信後に新しいCSVリンクが現れるまでポーリングしてダウンロード"""
    polls = MAX_WAIT_MIN * 60 // POLL_INTERVAL_SEC
    # "20260729" → "2026/07/29" 形式に変換（リンクタイトル内の日付と照合）
    date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}" if len(date_str) == 8 else ""

    for attempt in range(int(polls)):
        log.info(f"DLページ確認 {attempt + 1}/{int(polls)} 回目...")
        try:
            links = get_dl_links(session)
        except Exception as e:
            log.warning(f"DLページ取得エラー（次回リトライ）: {e}")
            time.sleep(POLL_INTERVAL_SEC)
            continue

        # 対象日付を含む 商品売上実績(日別) のリンクを検索
        new_links = [
            lnk for lnk in links
            if "商品売上実績" in lnk["title"]
            and "日別" in lnk["title"]
            and (date_fmt in lnk["title"] if date_fmt else lnk["created_at"] >= submitted_at - timedelta(minutes=2))
        ]

        if new_links:
            # 最新のものを取得
            target = max(new_links, key=lambda x: x["created_at"])
            log.info(f"新しいCSVを発見: {target['title']} (作成時: {target['created_at']})")
            r = session.get(target["url"])
            if r.status_code == 200 and len(r.content) > 1000:
                out_path.write_bytes(r.content)
                log.info(f"保存完了: {out_path} ({len(r.content):,} bytes)")
                return True
            else:
                log.warning(f"ダウンロード失敗 (status={r.status_code}, size={len(r.content)})")

        log.info(f"  → まだ未完了。{POLL_INTERVAL_SEC}秒後に再確認...")
        time.sleep(POLL_INTERVAL_SEC)

    log.error(f"{MAX_WAIT_MIN}分待ちましたがCSVが見つかりませんでした")
    return False


def run(target_date: datetime | None = None) -> str | None:
    cfg = load_config()
    date = target_date or (datetime.now() - timedelta(days=1))
    date_str = date.strftime("%Y%m%d")

    download_dir = (BASE_DIR / cfg["download_dir"]).resolve()
    download_dir.mkdir(exist_ok=True)
    out_path = download_dir / f"{date_str}.csv"

    if out_path.exists():
        log.info(f"{date_str}.csv はすでに存在します。スキップします。")
        return str(out_path)

    log.info(f"対象日付: {date.strftime('%Y/%m/%d')} のCSVダウンロード開始")

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    if not login(session, cfg):
        log.error("ログイン失敗")
        return None

    submitted_at = datetime.now()
    if not submit_csv_job(session, cfg, date_str):
        log.error("ジョブ送信失敗")
        return None

    log.info(f"ジョブ送信完了 ({submitted_at.strftime('%H:%M:%S')})。DLページを定期確認します...")

    if poll_and_download(session, submitted_at, out_path, date_str):
        return str(out_path)
    return None


def submit_visitors_job(session: requests.Session, date_str: str) -> bool:
    """
    取引レポート（全店舗・日別）のCSV生成ジョブを送信してDL0010020.phpに登録する。
    フロー:
      1. SAR60010010.php にGETアクセス → HTMLにCSVリンクが埋め込まれる
      2. HTMLから SAR60010030.php のCSV出力URLを抽出
      3. SAR60010030.php にGET → 「CSV作成指示」（onLoadチェーン）
      4. フォーム送信 → DL0010020.phpにCSVが登録される
    """
    year, month, day = date_str[:4], date_str[4:6], date_str[6:]
    params = {
        "ws_bussId": "7", "ws_programID": "SAR6", "ws_actType": "1",
        "ws_streFlg": "1", "ws_streCd": "0",  # 0=全店舗
        "ws_clsFlg": "3", "ws_periodFlg": "2",
        "ws_yearFrom": year, "ws_monthFrom": month, "ws_dayFrom": day,
        "ws_yearTo":   year, "ws_monthTo":   month, "ws_dayTo":   day,
        "ws_SerialNo": "1",
    }
    r = session.get(VISITORS_JOB_URL, params=params)
    if r.status_code != 200:
        log.error(f"取引レポートページ取得失敗 (status={r.status_code})")
        return False
    html = r.content.decode("shift_jis", errors="replace")

    # CSVダウンロードURL（SAR60010030.php?...&gs_FileName=csv...）を抽出
    m = re.search(r"openPdfWin\('(\./SAR60010030\.php\?[^']*gs_FileName=csv[^']*)'\s*,\s*'CSV'\)", html)
    if not m:
        log.error("CSVダウンロードリンクが見つかりません")
        return False

    rel = m.group(1).lstrip("./")
    csv_url = f"{BASE_URL}/SA/SAR6/{rel}"

    # SAR60010030.php にGET → 「CSV作成指示」（onLoad="document.CSV.submit()"）
    r1 = session.get(csv_url)
    html1 = r1.content.decode("shift_jis", errors="replace")
    if "document.CSV.submit()" not in html1:
        log.error("CSV作成指示ページが想定外")
        return False

    # フォーム送信 → DL0010020.phpへCSVを登録
    params1 = {}
    for inp in re.finditer(r'<INPUT[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html1, re.IGNORECASE):
        params1[inp.group(1)] = inp.group(2)
    action_m = re.search(r'<FORM[^>]+action=["\']([^"\']+)["\']', html1, re.IGNORECASE)
    action = action_m.group(1) if action_m else csv_url
    if not action.startswith("http"):
        action = BASE_URL + action

    r2 = session.get(action, params=params1)
    ok = r2.status_code == 200
    log.info(f"取引レポート ジョブ送信 {'成功' if ok else '失敗'} (status={r2.status_code})")
    return ok


def poll_and_download_visitors(session: requests.Session, submitted_at: datetime, out_path: Path, date_str: str = "") -> bool:
    """取引レポートCSVがDL0010020.phpに出るまでポーリングしてダウンロード"""
    polls = MAX_WAIT_MIN * 60 // POLL_INTERVAL_SEC
    # DLページのタイトルは「2026/08/01」形式（スラッシュ区切り）
    date_fmt = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}" if len(date_str) == 8 else ""

    for attempt in range(int(polls)):
        log.info(f"取引レポートDLページ確認 {attempt + 1}/{int(polls)} 回目...")
        try:
            links = get_dl_links(session)
        except Exception as e:
            log.warning(f"DLページ取得エラー: {e}")
            time.sleep(POLL_INTERVAL_SEC)
            continue

        new_links = [
            lnk for lnk in links
            if "取引レポート" in lnk["title"]
            and "全店" in lnk["title"]
            and (date_fmt in lnk["title"] if date_fmt else lnk["created_at"] >= submitted_at - timedelta(minutes=2))
        ]
        if new_links:
            target = max(new_links, key=lambda x: x["created_at"])
            log.info(f"取引レポートCSVを発見: {target['title']}")
            r = session.get(target["url"])
            if r.status_code == 200 and len(r.content) > 1000:
                out_path.write_bytes(r.content)
                log.info(f"保存完了: {out_path} ({len(r.content):,} bytes)")
                return True
            log.warning(f"ダウンロード失敗 (status={r.status_code}, size={len(r.content)})")

        log.info(f"  → まだ未完了。{POLL_INTERVAL_SEC}秒後に再確認...")
        time.sleep(POLL_INTERVAL_SEC)

    log.error(f"{MAX_WAIT_MIN}分待ちましたが取引レポートCSVが見つかりませんでした")
    return False


def run_visitors(target_date: datetime | None = None) -> str | None:
    """取引レポート（全店舗・日別）をダウンロードする"""
    cfg = load_config()
    date = target_date or (datetime.now() - timedelta(days=1))
    date_str = date.strftime("%Y%m%d")
    date_fmt = date.strftime("%Y.%m.%d")

    download_dir = (BASE_DIR / cfg["download_dir"]).resolve()
    download_dir.mkdir(exist_ok=True)

    # 既存ファイルがあればスキップ
    existing = list(download_dir.glob(f"*取引レポート*{date_fmt}*.csv"))
    if existing:
        log.info(f"取引レポートCSV ({date_str}) はすでに存在します。スキップします。")
        return str(existing[0])

    out_path = download_dir / f"全店_取引レポート_{date_str}.csv"
    log.info(f"取引レポート {date.strftime('%Y/%m/%d')} のダウンロード開始")

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    if not login(session, cfg):
        log.error("ログイン失敗")
        return None

    submitted_at = datetime.now()
    if not submit_visitors_job(session, date_str):
        log.error("取引レポート ジョブ送信失敗")
        return None

    if poll_and_download_visitors(session, submitted_at, out_path, date_str):
        return str(out_path)
    return None


if __name__ == "__main__":
    import sys
    target = None
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y%m%d")
    path = run(target)
    if path:
        print(f"ダウンロード完了: {path}")
    else:
        print("ダウンロード失敗")
        exit(1)
