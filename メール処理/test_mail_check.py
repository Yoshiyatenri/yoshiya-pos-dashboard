import csv
import json
from unittest.mock import MagicMock
from mail_check import load_config, load_processed_uids, save_processed_uids, match_keywords, append_log, CSV_FIELDNAMES, fetch_all_uids


def test_load_config_reads_json_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"imap_host": "example.com", "keywords": ["至急"]}),
        encoding="utf-8",
    )

    result = load_config(str(config_path))

    assert result["imap_host"] == "example.com"
    assert result["keywords"] == ["至急"]


def test_load_processed_uids_returns_none_when_file_missing(tmp_path):
    path = tmp_path / "processed_uids.json"

    result = load_processed_uids(str(path))

    assert result is None


def test_save_and_load_processed_uids_roundtrip(tmp_path):
    path = tmp_path / "processed_uids.json"

    save_processed_uids({"1", "2", "3"}, str(path))
    result = load_processed_uids(str(path))

    assert result == {"1", "2", "3"}


def test_match_keywords_returns_matched_list():
    result = match_keywords("【至急】オンライン集計のお願い", ["至急", "締め切り", "オンライン集計"])

    assert result == ["至急", "オンライン集計"]


def test_match_keywords_returns_empty_when_no_match():
    result = match_keywords("いつもお世話になっております", ["至急", "締め切り"])

    assert result == []


def test_append_log_writes_header_on_first_call(tmp_path):
    path = tmp_path / "mail_check_log.csv"
    row = {name: f"値-{name}" for name in CSV_FIELDNAMES}

    append_log(row, str(path))

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert reader.fieldnames == CSV_FIELDNAMES
    assert rows == [row]


def test_append_log_appends_without_duplicate_header(tmp_path):
    path = tmp_path / "mail_check_log.csv"
    row1 = {name: "1" for name in CSV_FIELDNAMES}
    row2 = {name: "2" for name in CSV_FIELDNAMES}

    append_log(row1, str(path))
    append_log(row2, str(path))

    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2


def test_fetch_all_uids_returns_uid_list():
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [b"1 2 3"])

    result = fetch_all_uids(fake_conn)

    assert result == [b"1", b"2", b"3"]
    fake_conn.uid.assert_called_once_with("search", None, "ALL")


def test_fetch_all_uids_raises_on_error_status():
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("NO", [b""])

    try:
        fetch_all_uids(fake_conn)
        assert False, "例外が発生するはず"
    except RuntimeError:
        pass
