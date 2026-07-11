import json
import zipfile
from datetime import date, datetime

from make_shufoo_csv import build_csv_rows, check_images_exist, collect_used_images, compute_period, format_datetime, load_config, parse_date, remove_used_images, resolve_image_filename, resolve_picked_image, write_csv, write_zip


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


def test_resolve_image_filename_uses_default_when_no_override():
    store = {"entry_id": "1", "store_id": "881827", "store_name": "テスト店"}
    assert resolve_image_filename(store, "default.JPG", {}) == "default.JPG"


def test_resolve_image_filename_uses_override_when_present():
    store = {"entry_id": "1", "store_id": "881863", "store_name": "天理店"}
    overrides = {"881863": "yasui_tenri.JPG"}
    assert resolve_image_filename(store, "yasui.JPG", overrides) == "yasui_tenri.JPG"


def test_build_csv_rows_produces_25_columns_per_store():
    stores = [
        {"entry_id": "20250221", "store_id": "881827", "store_name": "テスト店A"},
        {"entry_id": "20250221", "store_id": "881863", "store_name": "天理店"},
    ]
    start_dt = datetime(2026, 7, 9, 19, 0)
    end_dt = datetime(2026, 7, 11, 15, 0)
    overrides = {"881863": "special.JPG"}

    rows = build_csv_rows(stores, start_dt, end_dt, "テストタイトル", "default.JPG", overrides)

    assert len(rows) == 2
    assert len(rows[0]) == 25
    assert rows[0][:7] == [
        "20250221", "881827", "テスト店A",
        "2026/7/9 19:00", "2026/7/11 15:00", "テストタイトル", "default.JPG",
    ]
    assert rows[0][7:22] == [""] * 15
    assert rows[0][22:] == ["1", "", "N"]
    assert rows[1][6] == "special.JPG"


def test_write_csv_writes_header_and_rows_in_cp932(tmp_path):
    rows = [["20250221", "881827", "テスト店", "2026/7/9 19:00", "2026/7/11 15:00",
              "タイトル", "default.JPG"] + [""] * 15 + ["1", "", "N"]]
    csv_path = tmp_path / "output.csv"

    write_csv(rows, csv_path)

    text = csv_path.read_bytes().decode("cp932")
    assert "チラシ入稿ID" in text
    assert "テスト店" in text
    assert "default.JPG" in text


def test_collect_used_images_deduplicates_and_sorts():
    rows = [
        ["1", "881827", "店A", "s", "e", "t", "b.JPG"] + [""] * 15 + ["1", "", "N"],
        ["1", "881828", "店B", "s", "e", "t", "a.JPG"] + [""] * 15 + ["1", "", "N"],
        ["1", "881829", "店C", "s", "e", "t", "b.JPG"] + [""] * 15 + ["1", "", "N"],
    ]
    assert collect_used_images(rows) == ["a.JPG", "b.JPG"]


def test_check_images_exist_splits_existing_and_missing(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"dummy")

    existing, missing = check_images_exist(["a.JPG", "b.JPG"], tmp_path)

    assert existing == ["a.JPG"]
    assert missing == ["b.JPG"]


def test_write_zip_bundles_only_specified_images(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"image-a")
    (tmp_path / "b.JPG").write_bytes(b"image-b")
    zip_path = tmp_path / "out.zip"

    write_zip(["a.JPG"], tmp_path, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        assert z.namelist() == ["a.JPG"]
        assert z.read("a.JPG") == b"image-a"


def test_resolve_picked_image_copies_file_from_outside_base_dir(tmp_path):
    base_dir = tmp_path / "shufoo"
    base_dir.mkdir()
    outside_dir = tmp_path / "downloads"
    outside_dir.mkdir()
    picked_file = outside_dir / "chirashi.JPG"
    picked_file.write_bytes(b"image-bytes")

    result = resolve_picked_image(str(picked_file), base_dir)

    assert result == "chirashi.JPG"
    copied = base_dir / "chirashi.JPG"
    assert copied.exists()
    assert copied.read_bytes() == b"image-bytes"


def test_resolve_picked_image_does_not_copy_when_already_in_base_dir(tmp_path):
    base_dir = tmp_path / "shufoo"
    base_dir.mkdir()
    picked_file = base_dir / "chirashi.JPG"
    picked_file.write_bytes(b"image-bytes")

    result = resolve_picked_image(str(picked_file), base_dir)

    assert result == "chirashi.JPG"
    # コピー元と同一なので、ファイルは1つだけ存在する
    assert list(base_dir.iterdir()) == [picked_file]


def test_remove_used_images_deletes_specified_files(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"image-a")
    (tmp_path / "b.JPG").write_bytes(b"image-b")

    remove_used_images(["a.JPG"], tmp_path)

    assert not (tmp_path / "a.JPG").exists()
    assert (tmp_path / "b.JPG").exists()


def test_remove_used_images_skips_missing_files_without_error(tmp_path):
    # 存在しないファイル名を渡してもエラーにならないことを確認する
    remove_used_images(["not_exist.JPG"], tmp_path)
