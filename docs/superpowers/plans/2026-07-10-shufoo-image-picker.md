# SHUFOOツール 画像ファイルのダイアログ選択化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `日次業務/shufoo/make_shufoo_csv.py`で、画像ファイル名をキーボード入力する代わりに、Windowsのファイル選択ダイアログから選べるようにする。

**Architecture:** ダイアログを開く`pick_image_file`（対話・GUI依存、テスト対象外）と、選ばれたパスをbase_dir配下のファイル名に正規化する`resolve_picked_image`（純粋なファイルコピーロジック、ユニットテスト可能）に分離する。`main()`と`prompt_overrides`は`pick_image_file`を呼び出すよう変更する。

**Tech Stack:** Python 3.12標準ライブラリ（`tkinter.filedialog`, `shutil`, 既存の`pathlib`）、pytest

## Global Constraints

- コメント・ログ・print文のメッセージはすべて日本語で書く
- パターン選択・店舗選択の番号入力メニューは変更しない（画像ファイル名の指定方法のみ変更）
- 対話・GUI依存のコード（`pick_image_file`）はユニットテスト対象外とし、手動実行で確認する
- ファイルコピーロジック（`resolve_picked_image`）は純粋なファイル操作として切り出し、ユニットテストする

---

## ファイル構成

| ファイル | 変更内容 |
|---|---|
| `日次業務/shufoo/make_shufoo_csv.py` | `resolve_picked_image`, `pick_image_file`を追加。`main()`と`prompt_overrides`の画像ファイル名入力をダイアログ呼び出しに置き換え |
| `日次業務/shufoo/test_make_shufoo_csv.py` | `resolve_picked_image`のユニットテストを追加 |
| `日次業務/shufoo/使い方.md` | 画像ファイル名の指定方法をダイアログ選択に合わせて更新 |

---

### Task 1: 画像ファイルのダイアログ選択化

**Files:**
- Modify: `日次業務/shufoo/make_shufoo_csv.py`
- Test: `日次業務/shufoo/test_make_shufoo_csv.py`
- Modify: `日次業務/shufoo/使い方.md`

**Interfaces:**
- Consumes: 既存の`main()`, `prompt_overrides(stores)`（このタスクでシグネチャを変更する）
- Produces:
  - `resolve_picked_image(picked_path: str, base_dir: Path) -> str`（コピーが必要なら`base_dir`にコピーし、ファイル名を返す）
  - `pick_image_file(base_dir: Path) -> str`（ダイアログを開き、キャンセル時は再表示、選択後は`resolve_picked_image`を呼んでファイル名を返す）
  - `prompt_overrides(stores: list[dict], base_dir: Path) -> dict[str, str]`（引数に`base_dir`を追加）

- [ ] **Step 1: 失敗するテストを書く**

`test_make_shufoo_csv.py`に追記:

```python
from make_shufoo_csv import resolve_picked_image


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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: FAIL（`ImportError: cannot import name 'resolve_picked_image'`）

- [ ] **Step 3: `resolve_picked_image`を実装する**

`make_shufoo_csv.py`の先頭に`shutil`のimportを追加し、関数を追加:

```python
import shutil


def resolve_picked_image(picked_path, base_dir):
    """ダイアログで選ばれたパスをbase_dir配下のファイル名に正規化する。base_dir外のファイルはコピーする。"""
    picked = Path(picked_path)
    if picked.parent.resolve() != base_dir.resolve():
        shutil.copy2(picked, base_dir / picked.name)
    return picked.name
```

（`Path`は既存のimportに含まれている前提。含まれていなければ`from pathlib import Path`を追加する）

- [ ] **Step 4: テストが通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全16件、既存14件＋新規2件）

- [ ] **Step 5: `pick_image_file`を実装する**

`make_shufoo_csv.py`の先頭に`tkinter.filedialog`のimportを追加し、関数を追加（この関数はGUIダイアログに依存するためユニットテスト対象外。Step 9で手動確認する）:

```python
from tkinter import filedialog, Tk


def pick_image_file(base_dir):
    """Windowsのファイル選択ダイアログを開き、選ばれた画像ファイルのbase_dir内でのファイル名を返す。キャンセル時は再表示する。"""
    while True:
        root = Tk()
        root.withdraw()
        picked_path = filedialog.askopenfilename(
            initialdir=str(base_dir),
            title="画像ファイルを選択してください",
            filetypes=[("画像ファイル", "*.jpg;*.jpeg"), ("すべてのファイル", "*.*")],
        )
        root.destroy()
        if not picked_path:
            print("エラー: 画像ファイルが選択されませんでした。もう一度選択してください。")
            continue
        return resolve_picked_image(picked_path, base_dir)
```

- [ ] **Step 6: `main()`の画像ファイル名入力をダイアログ呼び出しに置き換える**

`make_shufoo_csv.py`の`main()`内、既定の画像ファイル名を`input()`で取得している箇所
（既存の空欄ガードのwhileループを含む）を、以下に置き換える:

```python
    default_image = pick_image_file(base_dir)
```

- [ ] **Step 7: `prompt_overrides`の画像ファイル名入力をダイアログ呼び出しに置き換える**

`prompt_overrides`の引数に`base_dir`を追加し、店舗選択後のファイル名`input()`呼び出しを
`pick_image_file(base_dir)`に置き換える:

```python
def prompt_overrides(stores, base_dir):
    """例外店舗（画像ファイル名が異なる店舗）の入力を受け付け、{store_id: filename}を返す。"""
    overrides = {}
    print("画像が異なる店舗はありますか？あれば番号を選んでください（終了は空Enter）")
    for i, store in enumerate(stores, start=1):
        print(f"{i}: {store['store_name']}")
    while True:
        choice = input("番号（空Enterで終了）: ").strip()
        if not choice:
            break
        try:
            index = int(choice)
            if not 1 <= index <= len(stores):
                raise ValueError
        except ValueError:
            print(f"エラー: 1〜{len(stores)}の番号を入力してください: {choice}")
            continue
        store = stores[index - 1]
        filename = pick_image_file(base_dir)
        overrides[store["store_id"]] = filename
    return overrides
```

`main()`内の呼び出し箇所も`prompt_overrides(pattern["stores"], base_dir)`に変更する
（`base_dir`は`main()`内で既に`load_config`より前に定義済み。呼び出し順序上、`prompt_overrides`を
呼ぶ前に`base_dir`が定義されていることを確認する）。

- [ ] **Step 8: 既存のユニットテストが引き続き通ることを確認する**

Run: `cd "日次業務/shufoo" && python -m pytest test_make_shufoo_csv.py -v`
Expected: PASS（全16件。`main`/`prompt_overrides`/`pick_image_file`関連の新規テストなし＝想定通り）

- [ ] **Step 9: 手動でダイアログ選択の一連の流れを確認する**

Run: `cd "日次業務/shufoo" && python make_shufoo_csv.py`

以下を試す:
1. パターン: `1`
2. 掲載開始日・終了日・タイトルを適当に入力
3. 既定の画像ファイル名の入力でファイル選択ダイアログが開くことを確認し、
   `日次業務/shufoo`フォルダ内の既存画像（例: `7.10-11.JPG`）を選択する
4. 例外店舗ありで進め、ダイアログでフォルダ外の画像（例えばデスクトップに置いた適当な画像）を
   選択し、選択後に自動的に`日次業務/shufoo`フォルダへコピーされることを確認する
5. ダイアログでキャンセル（×ボタン）を押した場合、エラーメッセージが表示されて
   ダイアログが再度開くことを確認する

Expected: 上記いずれも設計書通りに動作し、最終的にCSV・ZIPが生成される

- [ ] **Step 10: `使い方.md`を更新する**

`日次業務/shufoo/使い方.md`の「手順3: 質問に順番に答える」の表とその前後の説明を、
画像ファイル名の入力が「ファイル名を入力する」ではなく「ファイル選択ダイアログで選ぶ」に
変わったことが分かるように更新する。フォルダ外の画像を選んだ場合は自動コピーされる旨も追記する。

- [ ] **Step 11: コミット**

```bash
git add "日次業務/shufoo/make_shufoo_csv.py" "日次業務/shufoo/test_make_shufoo_csv.py" "日次業務/shufoo/使い方.md"
git commit -m "feat(shufoo): 画像ファイルの指定をファイル選択ダイアログに変更"
```
