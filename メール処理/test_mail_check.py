import json
import base64
from datetime import date
from unittest.mock import MagicMock
from mail_check import load_config, load_processed_uids, save_processed_uids, match_keywords, match_dates, fetch_all_uids, fetch_header, fetch_body


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


def test_match_dates_detects_received_date_kanji_format():
    result = match_dates("7月10日必着でお願いします", date(2026, 7, 10))

    assert result == ["7/10"]


def test_match_dates_detects_received_date_slash_format():
    result = match_dates("7/10までにご返信ください", date(2026, 7, 10))

    assert result == ["7/10"]


def test_match_dates_detects_next_day():
    result = match_dates("明日7/11までにお願いします", date(2026, 7, 10))

    assert result == ["7/11"]


def test_match_dates_handles_month_rollover():
    result = match_dates("8/1締め切りです", date(2026, 7, 31))

    assert result == ["8/1"]


def test_match_dates_no_match_returns_empty_list():
    result = match_dates("キーワードもない普通のメールです", date(2026, 7, 10))

    assert result == []


def test_match_dates_avoids_partial_match_false_positive():
    result = match_dates("7/10のイベントについて", date(2026, 7, 1))

    assert result == []


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


def test_fetch_header_parses_subject_from_date_and_received_date():
    encoded_subject = base64.b64encode("至急のご連絡".encode("utf-8")).decode("ascii")
    raw_header = (
        f"Subject: =?utf-8?B?{encoded_subject}?=\r\n"
        "From: Head Office <honbu@example.com>\r\n"
        "Date: Sat, 04 Jul 2026 09:00:00 +0900\r\n"
    ).encode("utf-8")
    raw_meta = b'1 (INTERNALDATE "04-Jul-2026 09:00:00 +0900" BODY[HEADER.FIELDS (SUBJECT FROM DATE)] {123}'
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(raw_meta, raw_header)])

    result = fetch_header(fake_conn, b"1")

    assert result["subject"] == "至急のご連絡"
    assert "honbu@example.com" in result["from"]
    assert result["date"] == "Sat, 04 Jul 2026 09:00:00 +0900"
    assert result["received_date"] == date(2026, 7, 4)


def test_fetch_body_returns_plain_text():
    raw_message = (
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "本文のテキストです。"
    ).encode("utf-8")
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(b"1 (BODY[])", raw_message)])

    result = fetch_body(fake_conn, b"1")

    assert result == "本文のテキストです。"


def test_fetch_body_strips_html_tags_when_only_html_available():
    raw_message = (
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        "<html><body><p>本文</p></body></html>"
    ).encode("utf-8")
    fake_conn = MagicMock()
    fake_conn.uid.return_value = ("OK", [(b"1 (BODY[])", raw_message)])

    result = fetch_body(fake_conn, b"1")

    assert "<" not in result
    assert "本文" in result


from unittest.mock import patch, MagicMock
import mail_check


def test_main_baseline_registers_existing_uids_without_logging(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    fake_conn = MagicMock()

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2"]), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2"}
    fake_send.assert_not_called()


def test_main_sends_notification_for_matched_new_mail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids({"1"}, str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "既読メール", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
        b"2": {"subject": "至急対応願います", "from": "b@example.com", "date": "d2", "received_date": date(2026, 7, 4)},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3", "received_date": date(2026, 7, 4)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2", b"3"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["件名"] == "至急対応願います"
    assert matches_arg[0]["ヒットキーワード"] == "至急"
    assert matches_arg[0]["緊急度"] == "高"

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2", "3"}


def test_main_skips_notification_when_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "普通の連絡", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)}}

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_not_called()
    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1"}


def test_main_continues_after_one_uid_fetch_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
        b"3": {"subject": "普通の連絡", "from": "c@example.com", "date": "d3", "received_date": date(2026, 7, 4)},
    }

    def fake_fetch_header(conn, uid):
        if uid == b"2":
            raise RuntimeError("壊れたメッセージ")
        return headers[uid]

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1", b"2", b"3"]), \
         patch.object(mail_check, "fetch_header", side_effect=fake_fetch_header), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["件名"] == "至急対応願います"

    saved = mail_check.load_processed_uids(str(tmp_path / "processed_uids.json"))
    assert saved == {"1", "2", "3"}


def test_main_logs_details_when_notification_send_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {b"1": {"subject": "至急対応願います", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)}}

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email", side_effect=RuntimeError("送信エラー")), \
         caplog.at_level("ERROR", logger="mail_check"):
        mail_check.main()

    assert any("送信に失敗しました" in message for message in caplog.messages)
    assert any("至急対応願います" in message for message in caplog.messages)


def test_main_sends_notification_for_date_matched_mail_without_keyword(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "明日の件について", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 10)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="7/11までにご確認をお願いします"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "中", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["ヒットキーワード"] == "日付(7/11)"


def test_main_sends_notification_for_keyword_matched_in_body_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "いつもの連絡です", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 4)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="本文中に至急の対応をお願いします"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["ヒットキーワード"] == "至急"


def test_main_prefers_keyword_label_when_both_keyword_and_date_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(
        '{"imap_host": "h", "imap_port": 143, "user": "u", "password": "p", '
        '"keywords": ["至急"], "anthropic_api_key": "k"}',
        encoding="utf-8",
    )
    mail_check.save_processed_uids(set(), str(tmp_path / "processed_uids.json"))
    fake_conn = MagicMock()
    headers = {
        b"1": {"subject": "至急のご連絡", "from": "a@example.com", "date": "d1", "received_date": date(2026, 7, 10)},
    }

    with patch.object(mail_check, "connect_imap", return_value=fake_conn), \
         patch.object(mail_check, "fetch_all_uids", return_value=[b"1"]), \
         patch.object(mail_check, "fetch_header", side_effect=lambda c, uid: headers[uid]), \
         patch.object(mail_check, "fetch_body", return_value="7/10までにご対応をお願いします"), \
         patch("mail_check.judge_urgency", return_value={
             "urgency": "高", "reply_needed": "要", "reason": "理由"
         }), \
         patch.object(mail_check, "send_notification_email") as fake_send:
        mail_check.main()

    fake_send.assert_called_once()
    matches_arg = fake_send.call_args[0][0]
    assert len(matches_arg) == 1
    assert matches_arg[0]["ヒットキーワード"] == "至急"
