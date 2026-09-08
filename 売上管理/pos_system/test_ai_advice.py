"""ai_advice.py のユニットテスト（Claude API部分）"""
import ai_advice


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


def test_call_ai_advice_success(monkeypatch):
    fake_response = _FakeResponse("■現状分析\nテスト分析\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessages(fake_response)

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    assert "現状分析" in result
    assert "施策1" in result


def test_call_ai_advice_missing_key():
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "")
    assert "APIキー" in result


def test_call_ai_advice_placeholder_key():
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "XXXXXXXXXX")
    assert "APIキー" in result


def test_call_ai_advice_no_package(monkeypatch):
    monkeypatch.setattr(ai_advice, "_anthropic_ok", False)
    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")
    assert "インストール" in result
