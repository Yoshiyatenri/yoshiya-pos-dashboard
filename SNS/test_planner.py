from unittest.mock import MagicMock
from planner import build_prompt, generate_plan_ideas


def test_build_prompt_includes_hashtags_and_captions():
    summary = {
        "top_hashtags": [("駄菓子", 2)],
        "top_videos_by_likes": [{"caption": "駄菓子屋開封動画", "likes": 300}],
    }
    prompt = build_prompt(summary)
    assert "#駄菓子（2件）" in prompt
    assert "駄菓子屋開封動画（いいね300件）" in prompt


def test_generate_plan_ideas_parses_response_lines():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(type="text", text="- 企画案1\n- 企画案2")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    summary = {"top_hashtags": [], "top_videos_by_likes": []}
    result = generate_plan_ideas(summary, api_key="dummy", client=fake_client)

    assert result == ["企画案1", "企画案2"]


def test_generate_plan_ideas_returns_empty_list_on_error():
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("APIエラー")

    summary = {"top_hashtags": [], "top_videos_by_likes": []}
    result = generate_plan_ideas(summary, api_key="dummy", client=fake_client)

    assert result == []
