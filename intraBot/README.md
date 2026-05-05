# intraBot

42 Tokyo の intra API と Discord を繋ぐ bot。

## できること

- `/link` … Discord アカウントと 42 アカウントを OAuth2 で紐付け
- `/status <login>` … 座席 / レベル / 合格課題+score / 進行中 / eval point / BH / freeze
- `/online [host_prefix] [pool_year] [pool_month]` … 現在校舎にいる cadet 一覧。座席前方一致 / piscine 受講時期 で絞り込み可
- `/slot add` `/slot list` `/slot del` … 自分の Find-a-peer slot を本人トークンで操作
- `/finder <project>` … 指定課題に合格 ∩ 在校中 の cadet を一覧、ボタンで DM
- レビュー通知 … 自分が evaluator/evaluated になると DM が届く (60s ポーリング)
- 新メンバー welcome … サーバー参加時に DM で `/link` を案内

## 起動手順

初回セットアップは [`SETUP.md`](./SETUP.md) を上から順に実施。`.env` ができたら:

```bash
make build
make up        # 別ターミナルで `ngrok http --url=<NGROK_DOMAIN> 4242` も起動しておく
make logs
```

## 必要な環境変数

`.env.example` 参照。Discord token / 42 OAuth UID+SECRET / ngrok 永続 URL の 3 セット。

## 担当者 / メイン言語

- メイン: Python 3.12 (discord.py 2.4 + aiohttp + aiosqlite)
- 担当: koyon
