"""Claude APIによるAI改善提案生成 と Word(.docx)エクスポート"""
import io

try:
    import anthropic
    _anthropic_ok = True
except ImportError:
    _anthropic_ok = False

try:
    from docx import Document
    _docx_ok = True
except ImportError:
    _docx_ok = False

_SYSTEM_PROMPT = (
    "あなたは駄菓子小売チェーンの経営コンサルタントです。"
    "与えられた実績数値だけを根拠に、日本語で店長向けの改善提案を書いてください。"
    "憶測や一般論だけの助言は避け、具体的な部門名・数値に基づいて指摘してください。"
    "売上の増減については、客数の変化によるものか客単価の変化によるものかを"
    "区別して分析し、集客施策（客数を増やす）と客単価向上施策（一人当たりの"
    "購入額を増やす）のどちらを優先すべきかを明確にしてください"
    "（客数データが「データなし」の場合は、この観点での分析は無理に行わないでください）。"
    "出力は「■現状分析」（3〜4文）と「■改善施策」（箇条書き3〜5個、それぞれ理由付き）の"
    "2つの見出しで構成してください。"
)


def call_ai_advice(store_label: str, period_label: str, metrics_text: str, api_key: str) -> str:
    """数値サマリーをもとにAI改善提案を生成する。失敗時はエラー文言を返す"""
    if not _anthropic_ok:
        return "⚠️ 生成に失敗しました（anthropicパッケージが未インストールです。`pip install anthropic`を実行してください）"
    if not api_key or "XXXXXXXXXX" in api_key:
        return "⚠️ 生成に失敗しました（Anthropic APIキーが設定されていません。config.jsonのanthropic_api_keyを確認してください）"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"【{store_label}　{period_label}】\n{metrics_text}",
            }],
        )
        text_blocks = [block.text for block in response.content if block.type == "text"]
        advice = "\n".join(text_blocks).strip()
        if not advice:
            return "⚠️ 生成に失敗しました（応答が空でした）"
        if getattr(response, "stop_reason", None) == "max_tokens":
            advice += "\n\n⚠️ 出力が上限に達したため、途中で切れている可能性があります。"
        return advice
    except anthropic.APIStatusError as e:
        return f"⚠️ 生成に失敗しました（APIエラー: HTTP {e.status_code}）"
    except anthropic.APIConnectionError:
        return "⚠️ 生成に失敗しました（API接続エラー。ネットワークを確認してください）"
    except Exception as e:
        return f"⚠️ 生成に失敗しました（{type(e).__name__}）"


def make_advice_docx(results: dict, period_label: str) -> bytes | None:
    """店舗ごとのAI改善提案をまとめた.docxをバイト列で返す"""
    if not _docx_ok:
        return None
    doc = Document()
    doc.add_heading(f"AI改善提案レポート　{period_label}", level=1)
    for store_label, advice_text in results.items():
        doc.add_heading(store_label, level=2)
        for line in advice_text.split("\n"):
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
