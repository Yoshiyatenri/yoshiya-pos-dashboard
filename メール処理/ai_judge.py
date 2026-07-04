"""Claude APIを使ってメールの緊急度・返信要否を判定する。"""
import re
import anthropic

CLAUDE_MODEL = "claude-sonnet-5"


def build_prompt(subject, body):
    """メール件名・本文からClaude APIに渡すプロンプト文を作る。"""
    return (
        "あなたは駄菓子店の店長を補佐するアシスタントです。\n"
        "以下のメールについて、緊急度と返信要否を判定してください。\n\n"
        f"件名: {subject}\n"
        f"本文:\n{body}\n\n"
        "次の形式で日本語で回答してください（他の文章は書かないでください）。\n"
        "緊急度: 高・中・低のいずれか1つ\n"
        "返信要否: 要・不要のいずれか1つ\n"
        "理由: 1文で簡潔に"
    )


def _extract_field(text, label):
    match = re.search(rf"{label}[:：]\s*(.+)", text)
    return match.group(1).strip() if match else None


def _parse_judgement(text):
    return {
        "urgency": _extract_field(text, "緊急度") or "不明",
        "reply_needed": _extract_field(text, "返信要否") or "不明",
        "reason": _extract_field(text, "理由") or "",
    }


def judge_urgency(subject, body, api_key, client=None):
    """メールの緊急度・返信要否をClaude APIで判定する。失敗時はAI判定失敗を返す。"""
    if client is None:
        client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(subject, body)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return _parse_judgement(text)
    except Exception as error:
        print(f"AI判定に失敗しました: {error}")
        return {
            "urgency": "AI判定失敗",
            "reply_needed": "AI判定失敗",
            "reason": str(error),
        }
