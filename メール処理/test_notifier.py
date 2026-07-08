from unittest.mock import MagicMock, patch
from notifier import build_email_body, send_notification_email


def test_build_email_body_includes_all_match_fields():
    matches = [
        {
            "差出人": "本部 <honbu@example.com>",
            "件名": "至急対応願います",
            "ヒットキーワード": "至急",
            "緊急度": "高",
            "返信要否": "要",
            "AI判断理由": "締め切りが本日のため",
        }
    ]

    body = build_email_body(matches)

    assert "1件" in body
    assert "本部 <honbu@example.com>" in body
    assert "至急対応願います" in body
    assert "ヒットキーワード: 至急" in body
    assert "緊急度: 高" in body
    assert "返信要否: 要" in body
    assert "締め切りが本日のため" in body


def test_build_email_body_includes_count_for_multiple_matches():
    matches = [
        {"差出人": "a@example.com", "件名": "件名1", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由1"},
        {"差出人": "b@example.com", "件名": "件名2", "ヒットキーワード": "締め切り",
         "緊急度": "中", "返信要否": "不要", "AI判断理由": "理由2"},
    ]

    body = build_email_body(matches)

    assert "2件" in body
    assert "件名1" in body
    assert "件名2" in body


def test_send_notification_email_sends_via_smtp_with_starttls():
    matches = [
        {"差出人": "a@example.com", "件名": "至急対応願います", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由"}
    ]
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "user": "tenri@okashinodepart.net",
        "password": "secret",
        "notify_to": "hanakiti0811@gmail.com",
    }
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp

    with patch("notifier.smtplib.SMTP", return_value=fake_smtp) as fake_smtp_cls:
        send_notification_email(matches, config)

    fake_smtp_cls.assert_called_once_with("smtp.example.com", 587, local_hostname="localhost")
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("tenri@okashinodepart.net", "secret")
    fake_smtp.send_message.assert_called_once()

    sent_message = fake_smtp.send_message.call_args[0][0]
    assert sent_message["From"] == "tenri@okashinodepart.net"
    assert sent_message["To"] == "hanakiti0811@gmail.com"
    assert "1件" in sent_message["Subject"]


def test_send_notification_email_raises_when_smtp_fails():
    matches = [
        {"差出人": "a@example.com", "件名": "件名", "ヒットキーワード": "至急",
         "緊急度": "高", "返信要否": "要", "AI判断理由": "理由"}
    ]
    config = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "user": "u",
        "password": "p",
        "notify_to": "to@example.com",
    }
    fake_smtp = MagicMock()
    fake_smtp.__enter__.return_value = fake_smtp
    fake_smtp.login.side_effect = RuntimeError("認証エラー")

    with patch("notifier.smtplib.SMTP", return_value=fake_smtp):
        try:
            send_notification_email(matches, config)
            assert False, "例外が発生するはず"
        except RuntimeError:
            pass
