# SHUFOOツール UP用フォルダ保存・使用画像の自動削除 設計書

作成日: 2026-07-11

## 背景・目的

これまで`make_shufoo_csv.py`はCSV・画像ZIPを`日次業務/shufoo/`直下に保存し、
画像ファイルもそのフォルダに置いたままだった。以下2点を変更する。

1. 最終成果物（CSV・画像ZIP）は、提出用に分かりやすいよう`日次業務/shufoo/UP用/`フォルダへ保存する
2. 画像ZIPに実際に使われた画像ファイルは、ZIP化した時点で`日次業務/shufoo/`から削除し、
   フォルダに使用済み画像が溜まらないようにする（画像自体はZIPの中に残るため実質的なデータ消失はない）

## 変更内容

### `main()`の変更

- `up_dir = base_dir / "UP用"`を定義し、存在しなければ`up_dir.mkdir(parents=True, exist_ok=True)`で作成する
- `csv_path`・`zip_path`の保存先を、これまでの`base_dir`から`up_dir`に変更する
  （画像の参照元は引き続き`base_dir`のまま。`check_images_exist(used_images, base_dir)`、
  `write_zip(existing, base_dir, zip_path)`の`folder`引数は変更しない）
- `write_zip`の完了後、ZIPに含まれた画像（`existing`のファイルすべて）を`base_dir`から削除する
  （新規関数`remove_used_images(image_filenames, folder)`を追加し、`main()`から呼び出す）

### 新規関数: `remove_used_images(image_filenames, folder) -> None`

- `image_filenames`（`existing`のリスト）それぞれについて`(folder / name).unlink()`で削除する
- 既に存在しないファイルを渡された場合はスキップする（`missing_ok=True`、二重実行時のエラー防止）
- 純粋なファイル操作のため、`check_images_exist`・`write_zip`と同様にユニットテストする

## エラー処理

- 画像ファイルが見つからない場合の既存の警告・続行確認フローは変更しない
  （`missing`のファイルは元々削除対象に含めない）
- `UP用`フォルダは初回実行時に自動作成されるため、事前準備は不要

## 影響範囲

- `日次業務/shufoo/make_shufoo_csv.py`のみ変更
- `使い方.md`を、保存先が`UP用`フォルダに変わったこと・使用済み画像が自動削除されることが
  分かるように更新する
