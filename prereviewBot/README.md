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

Libft v19.2 subject に厳密に従っています。チェックは順番に実行され、`make all` 失敗後でも構造的なフィードバック (README / Makefile 規則 / ヘッダ規則 / norminette など) は得られるよう先に走らせます。

| カテゴリ            | 項目                                                                                            |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| repo layout         | `.c` / `.h` がリポジトリ root に配置されているか (subject Chapter VI)                          |
| Makefile rules      | `cc` を使うか / `-std=c99` や `libtool` が含まれていないか / `ar` を使うか / 必須ルールが揃うか  |
| header rules        | `restrict` キーワードが入っていないか / bonus 時に `t_list` typedef が定義されているか          |
| norminette          | `ft_*.c` / `libft.h` (bonus 時は `*_bonus.{c,h}` も)                                            |
| compile flags       | 全 `*.c` を `gcc -Wall -Wextra -Werror -c` でコンパイル                                         |
| make targets        | `make all` / `clean` / `fclean` / `re` (bonus 時は `bonus` も) を順次実行                       |
| no relinking        | `make all` を 2 回叩いて 2 回目に再リンクが起きないこと (subject Chapter II)                    |
| required functions  | subject 記載の必須関数 34 個 (bonus 時は +9 個) が `libft.a` に定義されているか                 |
| no globals          | `nm libft.a` の D / B / C / G シンボルがないか (subject IV.1: global 宣言禁止)                  |
| behavioural smoke   | subject 規定の挙動を 30 種類以上のケースで `-fsanitize=address,undefined` 下で検証              |

> behavioural smoke は subject の Part 1 / Part 2 / Part 3 を網羅的にカバーし、AddressSanitizer + UndefinedBehaviorSanitizer + LeakSanitizer (LSAN exitcode 23) でメモリエラー / リーク / UB を検出します。テスト本体は `src/review/projects/libft_smoke.c`、追加項目はそこに足してください。

---

## 新しい課題を追加する手順 (例: ft_printf)

1. `src/review/projects/ft_printf.py` を作成し、`ProjectSpec` を定義する。
   - `required_mandatory_functions` / `forbidden_*` を subject に従って埋める
   - `expected_artifacts_mandatory` には `libftprintf.a` などビルド成果物
   - `check_builder` で再利用したい汎用チェックを並べる
2. 課題固有の挙動テストを `src/review/projects/ftprintf_smoke.c` 等に書き、専用の `tester` チェック関数 (`src/review/checks/printf_tester.py`) を追加して check_builder から呼ぶ。
3. `src/review/projects/registry.py` の末尾で `register(FT_PRINTF)` を呼ぶ。
4. `norminette_check` / `make_targets_check` / `compile_flags_check` / `repo_layout_check` / `makefile_rules_check` / `header_rules_check` / `required_functions_check` / `no_globals_check` / `no_relink_check` は project 非依存なのでそのまま流用可能。
5. `make restart` で bot を再起動すると `/prereview project:` の選択肢に自動的に出現します。

---

## セキュリティ上の注意

- `make all` / `gcc` の実行は、レビュー対象リポジトリに含まれるコードを **意図的に走らせる** 操作です。bot は Docker コンテナ内で `mem_limit=1g`, `pids_limit=256`, ネットワーク制限なし、`USER bot` (非 root) で動かしていますが、悪意ある相手からの URL を投げ込まれる前提のサービスとしては運用しないでください。
- 受け付けるリポジトリ URL は `https://github.com/...` のみに制限しています (`src/review/workspace.py`)。SSH/その他スキームは拒否されます。
- 一時ディレクトリは `/var/tmp/prereview/prereview-*` 配下に展開し、レビュー終了時 (および異常終了時) に削除されます。コンテナ自体を破棄すれば残骸も消えます。

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
        │   ├── no_relink.py
        │   ├── repo_layout.py
        │   ├── makefile_rules.py
        │   ├── header_rules.py
        │   ├── required_functions.py
        │   ├── globals.py
        │   └── tester.py
        └── projects/
            ├── base.py            # ProjectSpec
            ├── registry.py        # 名前 → ProjectSpec
            ├── libft.py
            └── libft_smoke.c      # behavioural smoke test テンプレート
```
