# manageMusic

`manageMusic` は **掃除の時間に流す曲のプレイリストを管理する Discord ボット + Web UI** です。
Discord 側でメンバーがスラッシュコマンドから曲を登録し、管理者は Web UI で一覧・削除を行います。

## 全体像

```
┌──────────────┐    /add title artist url     ┌──────────────┐
│  Discord     │ ───────────────────────────▶ │   bot (py)    │
└──────────────┘                              └──────┬───────┘
                                                     │ INSERT
                                              ┌──────▼───────┐
                                              │ SQLite       │
                                              │ ./data/*.db  │
                                              └──────▲───────┘
                                                     │ SELECT / DELETE
┌──────────────┐                              ┌──────┴───────┐
│  ブラウザ     │ ◀──────── HTML ─────────── │  web (FastAPI)│
└──────────────┘   localhost:8000             └──────────────┘
```

- DB は SQLite で `./data/manage_music.db` に保存し、`bot` / `web` の 2 コンテナで共有
- 重複判定は **URL 一致** のみ。重複時は Discord 上には「受け付けました」と返しつつ DB へは追加しない
- **曲の削除は Web UI からのみ** 可能(Bot 側に削除コマンドは置かない)

## 構成

```
manageMusic/
├── docker-compose.yml      # bot + web の 2 サービス定義
├── Makefile
├── .env.example
├── bot/                    # Discord ボット
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/bot.py
├── web/                    # FastAPI による管理 UI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       └── templates/index.html
└── data/                   # SQLite ファイル (gitignore)
```

## Discord コマンド

| コマンド                          | 動作                                       |
| --------------------------------- | ------------------------------------------ |
| `/add title artist url`           | 曲を登録。URL 重複時は無視 (本人には成功表示) |
| `/queue`                          | 最近追加された曲を最大10件表示            |
| `/help`                           | 使い方を表示                                |

## 必要な環境変数

| キー            | 必須 | 説明                                                                              |
| --------------- | ---- | --------------------------------------------------------------------------------- |
| `DISCORD_TOKEN` | ✅   | Discord bot のトークン                                                            |
| `GUILD_ID`      | -    | 指定すると、そのギルドへスラッシュコマンドを即時同期 (グローバルだと反映に最大1h) |

## 起動手順

```bash
cp .env.example .env
# .env に DISCORD_TOKEN を記入(必要に応じて GUILD_ID も)
make build
make up
```

起動後:
- Discord: ボットを招待し(scope: `bot` + `applications.commands`、権限: メッセージ送信)、`/add` を実行
- Web UI: ブラウザで <http://localhost:8000> を開く

## 担当者 / メイン言語

- 担当者: koyon
- 言語: Python 3.12
- 主要ライブラリ: discord.py / FastAPI / Jinja2 / SQLite (stdlib)
