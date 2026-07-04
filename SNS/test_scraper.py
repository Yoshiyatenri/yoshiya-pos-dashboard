import json
from scraper import extract_hashtags, extract_items_from_html, parse_item


def test_extract_hashtags_finds_all_tags():
    caption = "うまい棒紹介 #駄菓子 #うまい棒 楽しい"
    assert extract_hashtags(caption) == ["駄菓子", "うまい棒"]


def test_extract_hashtags_returns_empty_list_when_no_tags():
    assert extract_hashtags("ハッシュタグなしのキャプション") == []


def test_extract_items_from_html_parses_embedded_json():
    payload = {
        "__DEFAULT_SCOPE__": {
            "webapp.search-detail": {
                "searchResult": {"itemList": [{"item": {"id": "123"}}]}
            }
        }
    }
    html = (
        '<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'
        f"{json.dumps(payload)}</script></html>"
    )
    items = extract_items_from_html(html)
    assert items == [{"item": {"id": "123"}}]


def test_extract_items_from_html_returns_empty_list_when_missing():
    assert extract_items_from_html("<html></html>") == []


def test_parse_item_converts_raw_item_to_record():
    raw_item = {
        "item": {
            "id": "123",
            "desc": "駄菓子紹介 #駄菓子",
            "createTime": 1750000000,
            "author": {"uniqueId": "yoshiya_tenri"},
            "stats": {
                "diggCount": 10,
                "playCount": 100,
                "commentCount": 2,
                "shareCount": 1,
            },
        }
    }
    record = parse_item(raw_item, keyword="駄菓子")
    assert record["url"] == "https://www.tiktok.com/@yoshiya_tenri/video/123"
    assert record["hashtags"] == ["駄菓子"]
    assert record["likes"] == 10
    assert record["views"] == 100
    assert record["comments"] == 2
    assert record["shares"] == 1
    assert record["keyword"] == "駄菓子"
    assert record["posted_at"] == "2025-06-15"
