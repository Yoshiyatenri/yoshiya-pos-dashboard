"""傾向データから投稿企画案を生成する。"""
import anthropic

CLAUDE_MODEL = "claude-sonnet-5"


def build_prompt(summary):
    """傾向データからClaude APIに渡すプロンプト文を作る。"""
    hashtag_lines = "\n".join(
        f"- #{tag}（{count}件）" for tag, count in summary["top_hashtags"]
    )
    caption_lines = "\n".join(
        f"- {v['caption']}（いいね{v['likes']}件）"
        for v in summary["top_videos_by_likes"]
    )
    return (
        "あなたは駄菓子店のSNS担当者向けにアドバイスするマーケティング担当です。\n"
        "以下はTikTokで人気の駄菓子関連投稿の傾向データです。\n\n"
        f"よく使われるハッシュタグ:\n{hashtag_lines}\n\n"
        f"反応が良かった投稿:\n{caption_lines}\n\n"
        "この傾向を踏まえて、駄菓子店が撮影できる具体的な投稿企画案を3つ、"
        "箇条書きで日本語で提案してください。"
    )


def generate_plan_ideas(summary, api_key, client=None):
    """Claude APIを使って投稿企画案を生成する。失敗時は空リストを返す。"""
    if client is None:
        client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(summary)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    except Exception as error:
        print(f"企画案の生成に失敗しました: {error}")
        return []
