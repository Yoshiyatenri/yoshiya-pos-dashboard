import json

from make_shufoo_csv import load_config


def test_load_config_reads_patterns_and_stores(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "patterns": {
                "otoku": {
                    "label": "お買い得チラシ",
                    "csv_filename": "tirasi.csv",
                    "zip_filename": "tirasi_images.zip",
                    "stores": [
                        {"entry_id": "20250221", "store_id": "881827", "store_name": "テスト店"}
                    ],
                }
            }
        }),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["patterns"]["otoku"]["label"] == "お買い得チラシ"
    assert config["patterns"]["otoku"]["csv_filename"] == "tirasi.csv"
    assert config["patterns"]["otoku"]["stores"][0]["store_id"] == "881827"
