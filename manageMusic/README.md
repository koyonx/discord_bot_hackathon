# manageMusic

`manageMusic` は Discord サーバー内で音楽キューを管理するボットです。
実際の音声再生ではなく、チャットベースでプレイリスト管理を行います。

## できること

- `!add <曲名>` でキューに曲を追加
- `!queue` で現在のキューを表示
- `!remove <番号>` でキューから曲を削除
- `!clear` でキューを全削除
- `!help` でコマンド一覧を表示

## 必要な環境変数

- `DISCORD_TOKEN` - Discord bot のトークン
- `COMMAND_PREFIX` - コマンド接頭辞（省略時は `!`）

## 起動手順

```bash
cp .env.example .env
# .env に DISCORD_TOKEN を設定
make build
make up
```

起動後、Discord サーバーでボットを招待し、`!help` を実行して使い方を確認してください。

## 言語 / ライブラリ

- Python 3.12
- discord.py
- python-dotenv
