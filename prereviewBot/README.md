# prereviewBot

42Tokyo の課題リポジトリを Discord 経由で自動レビューする bot です。
`/prereview <project> <repository> <bonus>` を発行すると、指定された GitHub リポジトリに対して norminette / Makefile / コンパイルフラグ / スモークテストを走らせ、**失敗した項目だけ** を依頼者にのみ見える ephemeral メッセージとして返します。

- 担当: koyon
- 言語: Python 3.12 / discord.py 2.4

---

## 必要な環境変数

`.env.example` をコピーして `.env` を作成してください。

| 変数                            | 必須 | 用途                                                                       |
| ------------------------------- | ---- | -------------------------------------------------------------------------- |
| `DISCORD_TOKEN`                 | ✅   | Discord bot トークン                                                       |
| `DISCORD_GUILD_ID`              | -    | 開発時に特定ギルドへ即時同期するための ID。空のときはグローバル同期        |
| `REVIEW_CHECK_TIMEOUT_SECONDS`  | -    | 個別チェックのタイムアウト (デフォルト 120s)                               |
| `REVIEW_TOTAL_TIMEOUT_SECONDS`  | -    | レビュー全体のタイムアウト (デフォルト 600s, Discord defer の 15 分上限内) |

---

## 起動

```sh
cp .env.example .env
# .env を編集して DISCORD_TOKEN を設定
make build
make up
make logs    # bot のログを追う
make down    # 停止
```

`make help` でターゲット一覧が見られます。

---

## 使い方

1. bot を Discord サーバーに招待し、起動する。
2. 任意のチャンネルで以下を発行する:

   ```
   /prereview project:libft repository:https://github.com/<user>/<repo> bonus:False
   ```

3. **依頼者本人にのみ** 結果が ephemeral メッセージで届きます。
4. 失敗したチェックがある場合のみ、各チェックのコマンド・終了コード・stdout/stderr 抜粋が表示されます。すべて合格した場合は短い成功メッセージのみ。

### `<project>` で選べるもの

- `libft` — 現状サポート済み
- `ft_printf`, `get_next_line` — 拡張時に `src/review/projects/` 配下へ追加 (下記参照)

---

## レビュー対象として実行されるチェック (libft の場合)

| 項目                | 内容                                                                          |
| ------------------- | ----------------------------------------------------------------------------- |
| norminette          | `ft_*.c` / `libft.h` (bonus 指定時は `*_bonus.c` も) を `norminette` でチェック |
| make all/clean/fclean/re | 各ターゲットを順に実行し、終了コードを検証                                |
| make bonus          | `bonus=True` のときのみ追加で実行                                             |
| compile flags       | 全 `*.c` を `gcc -Wall -Wextra -Werror -c` でコンパイルできるか確認           |
| smoke tester        | `libft.h` を include した小さなテストハーネスを `libft.a` にリンクし実行     |

> スモークテストは `ft_strlen` / `ft_atoi` / `ft_isalpha` / `ft_strdup` の最低限の動作確認のみです。Tripouille/libftTester 等の本格的なテスターに置き換えたいときは `src/review/checks/tester.py` の `smoke_tester_check` を差し替えるか、別チェックとして並列実装してください。

---

## 新しい課題を追加する手順 (例: ft_printf)

1. `src/review/projects/ft_printf.py` を作成し、`ProjectSpec` を定義する。
   - `expected_artifacts_mandatory` には `libftprintf.a` などビルド成果物
   - `check_builder` に課題固有の検査ロジックを注入
2. `src/review/projects/registry.py` の末尾で `register(FT_PRINTF)` を呼ぶ。
3. 既存の `norminette_check` / `make_targets_check` / `compile_flags_check` はそのまま再利用可能。テスターだけは課題ごとに smoke C を書き直す必要があります (`src/review/checks/tester.py` を参考に)。
4. `make restart` で bot を再起動すると `/prereview project:` の選択肢に自動的に出現します。

---

## セキュリティ上の注意

- `make all` / `gcc` の実行は、レビュー対象リポジトリに含まれるコードを **意図的に走らせる** 操作です。bot は Docker コンテナ内で `mem_limit=1g`, `pids_limit=256`, ネットワーク制限なし、`USER bot` (非 root) で動かしていますが、悪意ある相手からの URL を投げ込まれる前提のサービスとしては運用しないでください。
- 受け付けるリポジトリ URL は `https://github.com/...` のみに制限しています (`src/review/workspace.py`)。SSH/その他スキームは拒否されます。
- 一時ディレクトリは `tmpfs` 上 (`/var/tmp/prereview`, 512MB) に展開し、レビュー終了時に削除されます。

---

## ディレクトリ構成

```
prereviewBot/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── README.md
├── requirements.txt
├── .env.example
└── src/
    ├── main.py                    # エントリポイント
    ├── bot.py                     # discord.py クライアント / スラッシュコマンド
    ├── config.py                  # 環境変数読み込み
    └── review/
        ├── check.py               # CheckResult / CommandRun / run_command
        ├── runner.py              # 全体オーケストレーション + タイムアウト
        ├── workspace.py           # tempdir + git clone
        ├── reporter.py            # 失敗のみを Discord 向けに整形
        ├── checks/
        │   ├── norminette.py
        │   ├── make_targets.py
        │   ├── compile_flags.py
        │   └── tester.py
        └── projects/
            ├── base.py            # ProjectSpec
            ├── registry.py        # 名前 → ProjectSpec
            └── libft.py
```
