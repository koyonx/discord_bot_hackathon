# discord_bot_hackathon

ハッカソンで開発する Discord bot 群を集約するモノレポです。
複数の bot を 1 リポジトリで管理し、bot ごとに使用言語/ライブラリが異なっていても、レビューや動作確認が誰でも同じ手順で行えるようにすることを目的とします。

---

## リポジトリ構成

```
discord_bot_hackathon/
├── README.md                  # このファイル(リポジトリ全体のルール)
├── .gitignore                 # 共通の除外設定
└── <bot-name>/                # bot 1 つにつき 1 フォルダ
    ├── README.md              # bot の概要・起動手順
    ├── Dockerfile             # 実行環境の定義(必須)
    ├── docker-compose.yml     # 起動構成の定義(必須)
    ├── Makefile               # 共通コマンドのエントリポイント(必須)
    ├── .env.example           # 環境変数のテンプレート(秘密情報は含めない)
    ├── .gitignore             # bot 固有の除外設定(必要に応じて)
    └── src/                   # 実装本体(言語に応じて app/, cmd/ などでも可)
```

`<bot-name>` は camelCase を推奨します(例: `welcomeBot`, `reminderBot`)。

---

## bot フォルダに必ず置くもの

bot ごとに使う言語/ライブラリは自由ですが、**他のメンバーが中身を知らなくてもレビュー・起動できる**状態を維持するため、以下は必須とします。

### 1. Docker 構成 (`Dockerfile` + `docker-compose.yml`)

- ローカル環境を汚さずに起動できるようにするため。
- `docker compose up` 一発で動く状態にしておくこと。
- 言語ランタイムや OS 依存パッケージのインストールは Dockerfile に閉じ込め、ホスト側に追加インストールを要求しない。

### 2. Makefile

レビュアー/チームメイトが言語に依存せず同じコマンドで bot を扱えるよう、最低限以下のターゲットを定義してください。

| ターゲット   | 役割                                          |
| ------------ | --------------------------------------------- |
| `make build` | Docker イメージをビルド                       |
| `make up`    | bot を起動(`docker compose up`)            |
| `make down`  | bot を停止                                    |
| `make logs`  | ログを表示                                    |
| `make lint`  | 静的解析/フォーマットチェック                 |
| `make test`  | テスト実行(テストが無い場合は no-op で可)  |

### 3. `.env.example`

- bot が必要とする環境変数(`DISCORD_TOKEN` など)のキーだけを列挙したテンプレート。
- **実際のトークンや API キーは絶対にコミットしない。** 実値は各自 `.env` に書き、`.gitignore` で除外する。

### 4. bot ごとの `README.md`

最低限、以下を書いておくこと。

- bot の目的(何をする bot か)
- 必要な環境変数
- 起動手順(`make build && make up` で動く想定)
- 担当者 / メイン言語

---

## 推奨事項

必須ではないものの、以下に従っておくとレビュー/引き継ぎがスムーズになります。

- **シークレットは絶対にコミットしない。** 万一コミットしてしまった場合は速やかにトークンを再発行する。
- **依存ロックファイルをコミットする。** (`package-lock.json`, `poetry.lock`, `requirements.txt`, `go.sum` など)
- **lint / formatter を導入する。** Python なら `ruff`、TS/JS なら `eslint` + `prettier` 等。`make lint` から呼べるようにする。
- **PR は bot フォルダ単位で出す。** 複数 bot をまたぐ変更はレビューしづらいので原則避ける。
- **ブランチ名は `feature/<bot-name>/<topic>` のような形式に揃える。** どの bot に対する作業かがひと目で分かるようにする。
- **共通化したい処理が出てきたら相談する。** 早すぎる共通化はせず、2〜3 個の bot で重複が確認できてから検討する。

---

## 新しい bot を追加するときの手順

1. ルート直下に `<bot-name>/` フォルダを作成する。
2. 上記の必須ファイル(Dockerfile / docker-compose.yml / Makefile / .env.example / README.md)を揃える。
3. `make build && make up` でローカル起動できることを確認する。
4. ブランチを切って PR を出す。
