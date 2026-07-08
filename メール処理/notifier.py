"""検知結果をまとめて通知メールとして送信する。"""
import smtplib
from email.message import EmailMessage


def build_email_body(matches):
    """検知したメールのリストから、まとめて1通分の本文テキストを組み立てる。"""
    separator = "-" * 40
    lines = [f"以下の該当メールを検知しました（{len(matches)}件）。", ""]

    for match in matches:
        lines.append(separator)
        lines.append(f"差出人: {match['差出人']}")
        lines.append(f"件名: {match['件名']}")
        lines.append(f"ヒットキーワード: {match['ヒットキーワード']}")
        lines.append(f"緊急度: {match['緊急度']}")
        lines.append(f"返信要否: {match['返信要否']}")
        lines.append(f"理由: {match['AI判断理由']}")
    lines.append(separator)

    return "\n".join(lines)


def send_notification_email(matches, config):
    """検知結果をまとめて通知メールとして送信する。失敗時は例外を呼び出し元に伝播させる。"""
    message = EmailMessage()
    message["Subject"] = f"メールチェック結果: {len(matches)}件検知"
    message["From"] = config["user"]
    message["To"] = config["notify_to"]
    message.set_content(build_email_body(matches))

    with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as smtp:
        smtp.starttls()
        smtp.login(config["user"], config["password"])
        smtp.send_message(message)
