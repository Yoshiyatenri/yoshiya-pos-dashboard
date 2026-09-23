# 従業員ポータル（天理店）

目標の自己採点・アンケート（匿名/記名）・提案（匿名/記名）をまとめたWebアプリ。
設計書: `docs/superpowers/specs/2026-09-23-employee-portal-design.md`

## セットアップ（ローカル）

```powershell
cd スタッフ管理\employee_portal
pip install -r requirements.txt -r requirements-dev.txt
copy config.example.json config.json
# config.json を開いて admin_password / general_password / secret_key を設定する
python app.py
```

ブラウザで `http://localhost:5000` を開く。`config.json`の`db_url`が空の場合はSQLite
（`employee_portal.db`）が自動的に使われる。

## テスト実行

```powershell
cd スタッフ管理\employee_portal
python -m pytest -v
```

## Supabase（本番DB）を使う場合

`config.json`の`db_url`にSupabaseの接続文字列を設定すると、自動的にPostgreSQLへ
切り替わる（起動時にテーブルが自動作成される）。POSシステムと同じSupabase
プロジェクトに、`employees` / `goals` / `goal_scores` / `surveys` /
`survey_questions` / `survey_responses` / `survey_answers` / `proposals`
の8テーブルが新規作成される（既存のPOSテーブルとは無関係）。

## Renderへのデプロイ

1. このリポジトリをRenderの「Web Service」として登録する
   （Root Directory: `スタッフ管理/employee_portal`）
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn "app:create_app()"`（`Procfile`があれば自動検出される）
4. Renderの「Environment」で以下の環境変数を設定する（`config.json`はGit管理外の
   ため、本番ではこちらを使う）
   - `EMPLOYEE_PORTAL_DB_URL`: SupabaseのPostgreSQL接続文字列
   - `EMPLOYEE_PORTAL_ADMIN_PASSWORD`: 店長用パスワード
   - `EMPLOYEE_PORTAL_GENERAL_PASSWORD`: 従業員共通パスワード
   - `EMPLOYEE_PORTAL_SECRET_KEY`: セッション用のランダムな文字列
5. デプロイ後、初回アクセス時に`init_schema()`が実行され、Supabase上にテーブルが
   自動作成される

## 手動での動作確認手順

1. 店長メニューから従業員を1名登録する
2. 同じ従業員に目標を1件登録する
3. 従業員としてログインし、名前を選択して目標に自己採点する
4. 店長メニューの「採点履歴」で記録が見えることを確認する
5. 店長メニューからアンケートを新規作成し、自由記述・選択式の質問を1問ずつ追加して
   公開する
6. 従業員としてアンケートに回答する
7. 店長メニューの「結果」で集計を確認し、「Excel」からダウンロードできることを
   確認する
8. 従業員として記名・匿名それぞれで提案を送信し、店長メニューの「提案一覧」で
   投稿者表示（匿名は「匿名」と表示）とステータス変更ができることを確認する
