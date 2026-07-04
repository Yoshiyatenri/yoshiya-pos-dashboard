from analyzer import top_hashtags, top_videos, summarize

SAMPLE_RECORDS = [
    {
        "url": "https://www.tiktok.com/@a/video/1",
        "keyword": "駄菓子",
        "caption": "うまい棒の食べ比べ",
        "hashtags": ["駄菓子", "うまい棒"],
        "likes": 100,
        "views": 1000,
        "comments": 5,
        "shares": 2,
        "posted_at": "2026-06-01",
    },
    {
        "url": "https://www.tiktok.com/@b/video/2",
        "keyword": "駄菓子",
        "caption": "駄菓子屋開封動画",
        "hashtags": ["駄菓子", "開封"],
        "likes": 300,
        "views": 5000,
        "comments": 20,
        "shares": 10,
        "posted_at": "2026-06-05",
    },
    {
        "url": "https://www.tiktok.com/@c/video/3",
        "keyword": "うまい棒",
        "caption": "うまい棒コンプリート",
        "hashtags": ["うまい棒"],
        "likes": 50,
        "views": 800,
        "comments": 1,
        "shares": 0,
        "posted_at": "2026-06-10",
    },
]


def test_top_hashtags_orders_by_count_descending():
    result = top_hashtags(SAMPLE_RECORDS, top_n=3)
    # Counter.most_commonは同数の場合、最初に出現した順（駄菓子→うまい棒）を保つ
    assert result == [("駄菓子", 2), ("うまい棒", 2), ("開封", 1)]


def test_top_videos_sorts_by_likes_descending():
    result = top_videos(SAMPLE_RECORDS, top_n=2, by="likes")
    assert [v["url"] for v in result] == [
        "https://www.tiktok.com/@b/video/2",
        "https://www.tiktok.com/@a/video/1",
    ]


def test_summarize_returns_expected_keys():
    summary = summarize(SAMPLE_RECORDS, top_n=5)
    assert summary["video_count"] == 3
    assert summary["keywords"] == ["うまい棒", "駄菓子"]
    assert summary["top_hashtags"][0] == ("駄菓子", 2)
    assert len(summary["top_videos_by_likes"]) == 3
