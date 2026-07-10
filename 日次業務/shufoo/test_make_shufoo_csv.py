import json
from datetime import date, datetime

from make_shufoo_csv import compute_period, format_datetime, load_config, parse_date


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


def test_parse_date_with_month_day_only_uses_default_year():
    result = parse_date("7/10", default_year=2026)
    assert result == date(2026, 7, 10)


def test_parse_date_with_full_year():
    result = parse_date("2026/7/10", default_year=2099)
    assert result == date(2026, 7, 10)


def test_parse_date_rejects_invalid_format():
    try:
        parse_date("2026-07-10", default_year=2026)
        assert False, "ValueErrorが発生するはず"
    except ValueError:
        pass


def test_compute_period_start_is_previous_day_19_00():
    start_dt, end_dt = compute_period(date(2026, 7, 10), date(2026, 7, 11))
    assert start_dt == datetime(2026, 7, 9, 19, 0)
    assert end_dt == datetime(2026, 7, 11, 15, 0)


def test_compute_period_handles_year_boundary():
    start_dt, end_dt = compute_period(date(2027, 1, 1), date(2027, 1, 3))
    assert start_dt == datetime(2026, 12, 31, 19, 0)
    assert end_dt == datetime(2027, 1, 3, 15, 0)


def test_format_datetime_matches_shufoo_style():
    assert format_datetime(datetime(2026, 7, 9, 19, 0)) == "2026/7/9 19:00"
