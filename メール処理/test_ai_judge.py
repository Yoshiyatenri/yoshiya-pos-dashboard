from unittest.mock import MagicMock
from ai_judge import build_prompt, judge_urgency


def test_build_prompt_includes_subject_and_body():
    prompt = build_prompt("至急のご連絡", "本文のテキストです。")

    assert "至急のご連絡" in prompt
    assert "本文のテキストです。" in prompt


def test_judge_urgency_parses_response():
    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(type="text", text="緊急度: 高\n返信要否: 要\n理由: 締め切りが本日のため")
    ]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    result = judge_urgency("至急のご連絡", "本文", api_key="dummy", client=fake_client)

    assert result == {
        "urgency": "高",
        "reply_needed": "要",
        "reason": "締め切りが本日のため",
    }


def test_judge_urgency_returns_failure_dict_on_error():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("APIエラー")

    result = judge_urgency("至急のご連絡", "本文", api_key="dummy", client=fake_client)

    assert result["urgency"] == "AI判定失敗"
    assert result["reply_needed"] == "AI判定失敗"
    assert "APIエラー" in result["reason"]
