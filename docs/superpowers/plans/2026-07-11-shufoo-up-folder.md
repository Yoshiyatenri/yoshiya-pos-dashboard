# SHUFOOツール UP用フォルダ保存・使用画像自動削除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `make_shufoo_csv.py`の出力先を`日次業務/shufoo/UP用/`フォルダに変更し、ZIP化した画像は元の`shufoo`フォルダから自動削除する。

**Architecture:** `main()`内で保存先パスを`base_dir`から`up_dir`（`base_dir / "UP用"`）に変更する。画像の参照元（コピー先・ZIP化元）は引き続き`base_dir`のまま。ZIP書き出し後、使用済み画像を`base_dir`から削除する`remove_used_images`を新規関数として切り出し、ユニットテストする。

**Tech Stack:** Python 3.12標準ライブラリ（`pathlib`）、pytest

## Global Constraints

- コメント・ログ・print文のメッセージはすべて日本語で書く
- 画像ファイルの参照元（ダイアログでコピーされる場所）は引き続き`日次業務/shufoo/`のまま変更しない
- CSV・画像ZIPの保存先のみ`日次業務/shufoo/UP用/`に変更する
- `UP用`フォルダが存在しない場合は自動作成する
- 削除対象は、今回のZIPに実際に含まれた画像ファイル（`check_images_exist`が返す`existing`）のみ。`missing`のファイルは削除対象に含めない

---

## ファイル構成

| ファイル | 変更内容 |
|---|---|
| `日次業務/shufoo/make_shufoo_csv.py` | `remove_used_images`を追加。`main()`の保存先パスと、ZIP後の画像削除呼び出しを追加 |
| `日次業務/shufoo/test_make_shufoo_csv.py` | `remove_used_images`のユニットテストを追加 |
| `日次業務/shufoo/使い方.md` | 保存先が`UP用`フォルダに変わったこと・使用済み画像の自動削除を追記 |

---

### Task 1: UP用フォルダ保存・使用画像の自動削除

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`
- Modify: `日次業務/shufoo/使い方.md`

**Interfaces:**
- Consumes: 既存の`write_zip(image_filenames, folder, zip_path)`、`check_images_exist`が返す`existing`（`list[str]`）
- Produces: `remove_used_images(image_filenames: list[str], folder: Path) -> None`（`folder`配下の指定ファイルを削除する。存在しないファイルはスキップする）

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py`に追記:

```python
from make_shufoo_csv import remove_used_images


def test_remove_used_images_deletes_specified_files(tmp_path):
    (tmp_path / "a.JPG").write_bytes(b"image-a")
    (tmp_path / "b.JPG").write_bytes(b"image-b")

    remove_used_images(["a.JPG"], tmp_path)

    assert not (tmp_path / "a.JPG").exists()
    assert (tmp_path / "b.JPG").exists()


def test_remove_used_images_skips_missing_files_without_error(tmp_path):
    # 存在しないファイル名を渡してもエラーにならないことを確認する
    remove_used_images(["not_exist.JPG"], tmp_path)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'remove_used_images'`）

- [ ] **Step 3: `remove_used_images`を実装する**

`make_shufoo_csv.py`に関数を追加（`write_zip`関数の直後など、ファイル操作系の関数のまとまりに置く）:

```python
def remove_used_images(image_filenames, folder):
    """ZIPに使用した画像ファイルをfolderから削除する。存在しないファイルはスキップする。"""
    for name in image_filenames:
        (folder / name).unlink(missing_ok=True)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全18件、既存16件＋新規2件）

- [ ] **Step 5: `main()`の保存先を`UP用`フォルダに変更する**

`make_shufoo_csv.py`の`main()`内、以下の箇所（現在の実装）:

```python
    csv_path = base_dir / pattern["csv_filename"]
    write_csv(rows, csv_path)

    zip_path = base_dir / pattern["zip_filename"]
    write_zip(existing, base_dir, zip_path)

    print(f"CSVを保存しました: {csv_path}（{len(rows)}件、例外{len(overrides)}件）")
    print(f"画像ZIPを保存しました: {zip_path}（{len(existing)}件）")
```

を、以下に置き換える:

```python
    up_dir = base_dir / "UP用"
    up_dir.mkdir(parents=True, exist_ok=True)

    csv_path = up_dir / pattern["csv_filename"]
    write_csv(rows, csv_path)

    zip_path = up_dir / pattern["zip_filename"]
    write_zip(existing, base_dir, zip_path)
    remove_used_images(existing, base_dir)

    print(f"CSVを保存しました: {csv_path}（{len(rows)}件、例外{len(overrides)}件）")
    print(f"画像ZIPを保存しました: {zip_path}（{len(existing)}件）")
    print(f"使用済み画像を削除しました: {', '.join(existing) if existing else 'なし'}")
```

`write_zip`の第2引数（画像の参照元フォルダ）は`base_dir`のまま変更しないこと
（画像のコピー先・ZIP化元は従来通り`shufoo`フォルダ）。

- [ ] **Step 6: 既存のユニットテストが引き続き通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全18件）

- [ ] **Step 7: 手動で一連の流れを確認する**

Run: `cd "日次業務/shufoo" && python make_shufoo_csv.py`

以下を試す（画像はダイアログでの手動選択が発生するため、実際に対話しながら確認する。
既存の`日次業務/shufoo/`内の画像を選ぶこと）:
1. パターン: `1`、開始日・終了日・タイトルを適当に入力
2. 既定の画像ファイル名でダイアログが開き、`shufoo`フォルダ内の既存画像を選ぶ
3. 例外店舗なしで進める
4. 完了後、以下を確認する:
   - `日次業務/shufoo/UP用/`フォルダが新規作成され、その中に`tirasi.csv`と`tirasi_images.zip`が保存されている
   - 手順2で選んだ画像ファイルが、`日次業務/shufoo/`フォルダから削除されている（ZIPの中には残っている）
   - `日次業務/shufoo/`直下には、もう`tirasi.csv`・`tirasi_images.zip`が作られない

Expected: 上記いずれも設計書通りに動作する

- [ ] **Step 8: `使い方.md`を更新する**

`日次業務/shufoo/使い方.md`の「手順4: 結果を確認する」を、保存先が`UP用`フォルダに
変わったことが分かるように更新する。また、「5. 覚えておいてほしいこと」に、
ZIP化した画像は`shufoo`フォルダから自動削除される（ZIPの中には残る）旨を追記する。

- [ ] **Step 9: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py" "日次業務/shufoo/使い方.md"
git commit -m "feat(shufoo): 出力先をUP用フォルダに変更し、使用済み画像を自動削除"
```
