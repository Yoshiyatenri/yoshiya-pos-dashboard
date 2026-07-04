import json
from mail_check import load_config


def test_load_config_reads_json_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"imap_host": "example.com", "keywords": ["至急"]}),
        encoding="utf-8",
    )

    result = load_config(str(config_path))

    assert result["imap_host"] == "example.com"
    assert result["keywords"] == ["至急"]
