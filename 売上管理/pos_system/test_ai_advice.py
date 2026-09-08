"""ai_advice.py のユニットテスト（Claude API部分）"""
import io

from docx import Document

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
