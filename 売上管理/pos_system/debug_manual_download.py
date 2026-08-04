"""
一時利用: Netdoa NX で日付指定のCSV生成命令を送信し、生成完了を待ってダウンロードする単発スクリプト。
対象帳票（すべて店舗:6 天理店）:
  - 天理店中分類別分類売上一覧 (SACL)
  - 天理店大分類別時間帯販売   (SATS)
  - 取引レポート(店舗別)       (SAR6 serialNo=0)
  - 取引レポート(レジ別)       (SAR6 serialNo=1)
使い方: python debug_manual_download.py 20260713
"""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import download as dl

STORE_CODE = "6"
OUT_DIR = Path(__file__).parent / "downloads" / "manual"
OUT_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL_SEC = 60
MAX_WAIT_MIN = 15


def submit_form_chain(session, url):
    """openCsvWin/openPdfWin が指すURLをGETし、返ってきたonLoadフォームを再現送信する"""
    r = session.get(url)
    html = r.content.decode("shift_jis", errors="replace")

    params = {}
    for inp in re.finditer(r'<INPUT[^>]+name=["\'](\w+)["\'][^>]+value=["\']([^"\']*)["\']', html, re.IGNORECASE):
        params[inp.group(1)] = inp.group(2)
    action_m = re.search(r'<FORM[^>]+action=["\']([^"\']+)["\']', html, re.IGNORECASE)
    method_m = re.search(r'method=["\'](\w+)["\']', html, re.IGNORECASE)
    if not action_m:
        print(f"  [失敗] フォームが見つかりません: {html[:200]}")
        return False
    action = action_m.group(1)
    if not action.startswith("http"):
        action = dl.BASE_URL + "/" + action
    method = (method_m.group(1) if method_m else "get").lower()

    r2 = session.get(action, params=params) if method == "get" else session.post(action, data=params)
    html2 = r2.content.decode("shift_jis", errors="replace")
    text2 = re.sub(r"<[^>]+>", " ", html2)
    text2 = re.sub(r"\s+", " ", text2).strip()
    ok = "作成します" in text2
    print(f"  {'[OK]' if ok else '[?]'} {text2[:80]}")
    return ok


def submit_sacl(session, date):
    url = (
        f"{dl.BASE_URL}/CsvArgsMake.php?gs_programId=SACL&gs_bussId=7&gs_bussSerialNo=6"
        f"&gs_streFlg=3&gs_streCd={STORE_CODE}&gs_clsFlg=3&gs_clsCd=0&gs_smlClsCd=0"
        "&gs_catDscCd=&gs_attribCd=&gs_makerCd=&gs_brgnCd=&gs_planCd="
        f"&gs_periodFlg=2&gs_yearFrom={date:%Y}&gs_monthFrom={date:%m}&gs_dayFrom={date:%d}"
        f"&gs_yearTo={date:%Y}&gs_monthTo={date:%m}&gs_dayTo={date:%d}"
        f"&gs_weekStartFrom={date:%Y/%m/%d}&gs_weekStartTo={date:%Y/%m/%d}"
        "&gs_yearFrom_C=&gs_monthFrom_C=&gs_dayFrom_C=&gs_yearTo_C=&gs_monthTo_C=&gs_dayTo_C="
        "&gs_weekStartFrom_C=1999/11/28&gs_weekStartTo_C=1999/11/28"
        "&gs_nonActPeriod=&gs_nonActYear=&gs_nonActMonth=&gs_nonActDay=&gs_nonActSeasonKbn="
        "&gs_loginCompCd=2269&gs_loginStreCd=1&gs_loginUserId=yoshiya&gs_loginUserSerialCd=8313"
        "&gs_srchFlg=&gs_sortFlg=&gs_orderByFlg=&gs_rankRowNum="
    )
    print("[送信] 中分類別分類売上一覧 (SACL)")
    session.get(f"{dl.BASE_URL}/SA/SACL/SACL0010010.php", params={"ws_bussId": "7"})
    return submit_form_chain(session, url)


def submit_sats(session, date):
    url = (
        f"{dl.BASE_URL}/CsvArgsMake.php?gs_programId=SATS&gs_bussId=7&gs_bussSerialNo=2"
        f"&gs_streFlg=3&gs_streCd={STORE_CODE}&gs_clsFlg=3&gs_clsCd=0&gs_smlClsCd=0"
        "&gs_catDscCd=&gs_attribCd=&gs_makerCd=&gs_brgnCd=&gs_planCd="
        f"&gs_periodFlg=2&gs_yearFrom={date:%Y}&gs_monthFrom={date:%m}&gs_dayFrom={date:%d}"
        f"&gs_yearTo={date:%Y}&gs_monthTo={date:%m}&gs_dayTo={date:%d}"
        f"&gs_weekStartFrom={date:%Y/%m/%d}&gs_weekStartTo={date:%Y/%m/%d}"
        "&gs_yearFrom_C=&gs_monthFrom_C=&gs_dayFrom_C=&gs_yearTo_C=&gs_monthTo_C=&gs_dayTo_C="
        "&gs_weekStartFrom_C=1999/11/28&gs_weekStartTo_C=1999/11/28"
        "&gs_nonActPeriod=&gs_nonActYear=&gs_nonActMonth=&gs_nonActDay=&gs_nonActSeasonKbn="
        "&gs_loginCompCd=2269&gs_loginStreCd=1&gs_loginUserId=yoshiya&gs_loginUserSerialCd=8313"
        "&gs_srchFlg=&gs_sortFlg=&gs_orderByFlg=&gs_rankRowNum="
    )
    print("[送信] 大分類別時間帯販売 (SATS)")
    session.get(f"{dl.BASE_URL}/SA/SATS/SATS0010010.php", params={"ws_bussId": "7"})
    return submit_form_chain(session, url)


def submit_sar6(session, date, serial_no, label):
    url = (
        f"{dl.BASE_URL}/SA/SAR6/SAR60010030.php?gs_programId=SAR6&gs_loginCompCd=2269&gs_loginStreCd=1"
        f"&gs_loginUserId=yoshiya&gs_loginUserSerialCd=8313&gs_streFlg=3&gs_streCd={STORE_CODE}&gs_periodFlg=2"
        f"&gs_yearFrom={date:%Y}&gs_monthFrom={date:%m}&gs_dayFrom={date:%d}"
        f"&gs_yearTo={date:%Y}&gs_monthTo={date:%m}&gs_dayTo={date:%d}"
        f"&gs_weekStartFrom={date:%Y/%m/%d}&gs_weekStartTo={date:%Y/%m/%d}"
        f"&gs_cstCnt=&gs_FileName=csv&gs_SerialNo={serial_no}&gs_flg=2"
    )
    print(f"[送信] 取引レポート({label}) (SAR6 serialNo={serial_no})")
    session.get(f"{dl.BASE_URL}/SA/SAR6/SAR60010010.php", params={"ws_bussId": "7"})
    return submit_form_chain(session, url)


def download_matching(session, keyword, submitted_at, label):
    links = dl.get_dl_links(session)
    matches = [
        lnk for lnk in links
        if keyword in lnk["title"]
        and ("天理店" in lnk["title"] or "店舗:6" in lnk["title"])
        and lnk["created_at"] >= submitted_at - timedelta(minutes=1)
    ]
    if not matches:
        return None
    target = max(matches, key=lambda x: x["created_at"])
    r = session.get(target["url"])
    if r.status_code != 200 or len(r.content) < 10:
        print(f"  [失敗] {label} (status={r.status_code})")
        return None
    safe = keyword.replace("(", "_").replace(")", "").replace("【", "_").replace("】", "")
    ts = target["created_at"].strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{safe}_{ts}.csv"
    out_path.write_bytes(r.content)
    print(f"  [保存] {label} -> {out_path} ({len(r.content):,} bytes)")
    return out_path


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    date = datetime.strptime(date_str, "%Y%m%d")
    print(f"対象日: {date:%Y/%m/%d}  対象店舗: {STORE_CODE}")

    cfg = dl.load_config()
    session = dl.requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    if not dl.login(session, cfg):
        print("ログイン失敗")
        return
    session.post(dl.BASE_URL + "/HM/HM0010010.php", data={"ws_bussId": "1"})

    submitted_at = datetime.now()
    targets = [
        ("中分類別分類売上一覧", lambda: submit_sacl(session, date)),
        ("大分類別時間帯販売", lambda: submit_sats(session, date)),
        ("取引レポート (店舗別)", lambda: submit_sar6(session, date, "0", "店舗別")),
        ("取引レポート (レジ別)", lambda: submit_sar6(session, date, "1", "レジ別")),
    ]
    for keyword, fn in targets:
        fn()

    print(f"生成命令送信完了 ({submitted_at:%H:%M:%S})。{POLL_INTERVAL_SEC}秒ごとにDLページを確認します...")

    pending = {kw for kw, _ in targets}
    polls = MAX_WAIT_MIN * 60 // POLL_INTERVAL_SEC
    for attempt in range(int(polls)):
        time.sleep(POLL_INTERVAL_SEC)
        print(f"確認 {attempt + 1}/{int(polls)} 回目...")
        for keyword in list(pending):
            if download_matching(session, keyword, submitted_at, keyword):
                pending.discard(keyword)
        if not pending:
            break

    if pending:
        print(f"未取得のまま終了: {pending}")
    else:
        print("4件すべて取得完了")


if __name__ == "__main__":
    main()
