"""ai_advice.py のユニットテスト（Claude API部分）"""
import io

from docx import Document

import ai_advice


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason


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


def test_call_ai_advice_prompt_instructs_customer_breakdown(monkeypatch):
    captured = {}

    class _FakeMessagesCapture:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse("■現状分析\nテスト\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessagesCapture()

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    system_prompt = captured["system"]
    assert "客数" in system_prompt
    assert "客単価" in system_prompt
    assert "集客" in system_prompt


def test_call_ai_advice_prompt_ogata_guidance_for_tenri(monkeypatch):
    captured = {}

    class _FakeMessagesCapture:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse("■現状分析\nテスト\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessagesCapture()

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    system_prompt = captured["system"]
    assert "目的買い" in system_prompt
    assert "品揃え" in system_prompt
    assert "ついで買い" not in system_prompt


def test_call_ai_advice_prompt_sonota_guidance_for_other_stores(monkeypatch):
    captured = {}

    class _FakeMessagesCapture:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse("■現状分析\nテスト\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessagesCapture()

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    ai_advice.call_ai_advice("十三店", "2026年6月", "売上: 100円", "sk-test-key")

    system_prompt = captured["system"]
    assert "ついで買い" in system_prompt
    assert "陳列" in system_prompt
    assert "目的買い" not in system_prompt


def test_call_ai_advice_prompt_instructs_impact_amount_priority(monkeypatch):
    captured = {}

    class _FakeMessagesCapture:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse("■現状分析\nテスト\n■改善施策\n- 施策1")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessagesCapture()

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    system_prompt = captured["system"]
    assert "影響額" in system_prompt
    assert "pt" in system_prompt


def test_call_ai_advice_truncated(monkeypatch):
    fake_response = _FakeResponse("■現状分析\n途中まで", stop_reason="max_tokens")

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.messages = _FakeMessages(fake_response)

    monkeypatch.setattr(ai_advice.anthropic, "Anthropic", _FakeAnthropic)

    result = ai_advice.call_ai_advice("天理店", "2026年6月", "売上: 100円", "sk-test-key")

    assert "途中まで" in result
    assert "上限に達した" in result


def test_make_advice_docx_contains_all_stores():
    results = {
        "天理店": "■現状分析\nテスト\n■改善施策\n- 施策1",
        "本店": "⚠️ 生成に失敗しました（APIエラー）",
    }

    data = ai_advice.make_advice_docx(results, "2026年6月")

    assert data is not None
    doc = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "天理店" in text
    assert "本店" in text
    assert "施策1" in text
    assert "2026年6月" in text


def test_make_advice_docx_no_package(monkeypatch):
    monkeypatch.setattr(ai_advice, "_docx_ok", False)
    assert ai_advice.make_advice_docx({"店": "文"}, "2026年6月") is None
