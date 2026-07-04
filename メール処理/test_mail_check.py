import json
from mail_check import load_config, load_processed_uids, save_processed_uids


def test_load_config_reads_json_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"imap_host": "example.com", "keywords": ["至急"]}),
        encoding="utf-8",
    )

    result = load_config(str(config_path))

    assert result["imap_host"] == "example.com"
    assert result["keywords"] == ["至急"]


def test_load_processed_uids_returns_none_when_file_missing(tmp_path):
    path = tmp_path / "processed_uids.json"

    result = load_processed_uids(str(path))

    assert result is None


def test_save_and_load_processed_uids_roundtrip(tmp_path):
    path = tmp_path / "processed_uids.json"

    save_processed_uids({"1", "2", "3"}, str(path))
    result = load_processed_uids(str(path))

    assert result == {"1", "2", "3"}
