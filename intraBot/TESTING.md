# intraBot テストシナリオ

各 slash command + background task の **happy / negative / edge** ケースを網羅。
レビュアーがそのまま手で確認できる粒度で書いてあります。

---

## 0. 事前準備

- `make build && make up` で bot 起動 (起動ログに `slash commands synced ... (10 cmds)` が出ること)
- ngrok を **永続 static domain** で起動 (`ngrok http --url=<NGROK_DOMAIN> 4242`)
- テストサーバーに **2 つの Discord アカウント** を入れる
  - **A**: 募集者 / 操作主役
  - **B**: 候補者 / 受け手役
- A・B 両方とも `/link` で 42 アカウントとの紐付けを完了

---

## 1. `/link`

| ケース | 操作 | 期待結果 |
|---|---|---|
| Happy | `/link` → DM の URL → 42 で `Authorize` | DM `✅ 紐付け完了 (login: xxx)`、`users` テーブル更新 |
| 再 link | 既に紐付け済の状態で `/link` | 新しい state で URL 再発行 |
| DM 拒否 | サーバー設定で intraBot からの DM を拒否 → `/link` | ephemeral で `DM が送れませんでした` |
| state 失効 | URL を発行して 10 分超 → URL 踏む | callback ページで `state エラー` |

---

## 2. `/status <login>`

| ケース | 入力 | 期待結果 |
|---|---|---|
| Happy | `/status kkuramot` | embed: 座席 / level / 合格 / 進行中 / eval point / BH / freeze |
| 在校中 | 在校中の人 | 🪑 `f3r1p1` (在校中) |
| オフライン | 不在の人 | 🪑 `オフライン (最終: f3r1p1)` |
| 不在 user | `/status notexist123` | ❌ user `notexist123` が見つかりません |
| Piscine 中 | piscine 期間中の人 | 42cursus エントリが無いので C Piscine の値 (期待動作) |

> 注: BH は API の `blackholed_at` をそのまま表示。intra UI の表示と乖離するケースがある (内部仕様で原因不明)。

---

## 3. `/online`

| ケース | 入力 | 期待結果 |
|---|---|---|
| Happy | `/online` | 在校中全員 (host 順) |
| host filter | `/online host_prefix:f3` | host が `f3*` だけ |
| pool filter | `/online pool_year:2025 pool_month:march` | 2025-03 piscine 出身のみ |
| 複合 | `/online host_prefix:f3 pool_year:2025` | AND 絞込 |
| 全 0 | 深夜 (誰もいない) | `現在校舎にいる人はいません 🌃` |
| 過剰件数 | 80 人超 | embed 末尾に `... 他 N 人` |

---

## 4. `/finder <project>`

| ケース | 入力 | 期待結果 |
|---|---|---|
| autocomplete | `/finder lib` 入力中 | `libft`, `libasm` などの候補が表示される |
| Happy | `/finder libft` | embed + Select dropdown |
| Select 紐付け済 | DM 送信先が `/link` 済 | A: `📨 DM を送りました` / B: `xxx さんが呼んでいます` の DM |
| Select 未紐付け | DM 送信先が未紐付け | `intra で Find a peer から呼んでください` |
| 不在 project | `/finder cp` (存在しない) | ❌ + 候補一覧 (`cpp-module-00` 等) |
| 合格者 0 | 新出題 project | 🤔 `Tokyo にまだ合格者がいません` |
| 在校 0 | 深夜の合格者あり project | 🌃 `合格者は N 人いますが今校舎に居ません` |

---

## 5. `/find_evaluator <project>`

| ケース | 操作 (A=募集, B=候補) | 期待結果 |
|---|---|---|
| Happy | A: `/find_evaluator libft` (B が紐付け済 + 在校 + libft 合格) | A: 候補数表示 + 送信成功一覧 / B: DM + 🙋 Accept ボタン |
| Accept | B: 🙋 押下 | A: DM `🙋 B が引き受けました` / B のメッセージ: `応答済` でボタン無効化 |
| 同時複数 Accept | 候補 C も Accept | A は 2 回 DM を受ける (ベスト 1 を A が選ぶ前提) |
| 候補ゼロ | A: 在校中合格者なし | 🌃 メッセージ |
| 紐付け済ゼロ | 在校中合格者がいるが Discord 連携 0 | `Discord 連携済が 0 人` メッセージ |
| 募集者 DM 拒否 | A が DM 拒否 + B が Accept | B にエラー表示 (募集者通知失敗) |

---

## 6. `/help`

| ケース | 期待結果 |
|---|---|
| Happy | 登録済 slash command 一覧 embed (group/subcommand 込み) |

---

## 7. `/freeze_guide`

| ケース | 期待結果 |
|---|---|
| Happy | freeze 申請手順の embed (静的) |

---

## 8. `/follow`

| ケース | 操作 | 期待結果 |
|---|---|---|
| add | `/follow add kkuramot` | `👁 kkuramot をフォローしました` |
| add 不在 | `/follow add notexist123` | ❌ user not found |
| add 重複 | 既にフォロー中 | 上書き (idempotent) |
| list | `/follow list` | フォロー中 cadet の embed |
| remove | `/follow remove kkuramot` | 🚫 解除 |
| remove 未登録 | `/follow remove unknown_login` | `フォローしていません` |
| **入室通知** | フォロー中の人が **新規入室** (= 前回 poll で居なかった) | DM `👁 xxx が yyy にログイン` (60s 以内) |
| 起動直後 | 起動時点で在校中だった人 | 通知されない (first_poll で吸収) |

---

## 9. `/slot add|list|del`

| ケース | 入力 | 期待結果 |
|---|---|---|
| add | `/slot add 2026-05-10T14:00 60` | ✅ slot 追加 + intra で確認 |
| add 不正分 | `/slot add 2026-05-10T14:07 60` | ❌ 15 分の倍数 |
| add 過去 | 過去日付 | API エラー |
| add 重複 | 既存と被る時間帯 | API エラー |
| list | `/slot list` | embed + Select dropdown |
| list cancel | Select で選択 | 🗑 削除完了 |
| del | `/slot del <id>` | 🗑 削除完了 |
| del 不在 | 存在しない id | ❌ |
| 未紐付け | `/link` 前に slot 系 | `先に /link を` |

---

## 10. `/events`

| ケース | 入力 | 期待結果 |
|---|---|---|
| list | `/events list` | 今後 30 日 (区切り線で 1 ブロック=1 イベント) |
| past | `/events list past:true` | 過去 30 日 |
| kind | `/events list kind:exam` | exam だけ (`/v2/exams` から取得統合) |
| theme | `/events list theme:python` | theme 名部分一致 |
| show event | `/events show <event_id>` | 詳細 embed |
| show exam | `/events show <exam_id>` | 詳細 embed (events で 404 → exams フォールバック) |
| show 不在 | 存在しない id | ❌ events / exams どちらにも無い |
| register event | `/events register <event_id>` | ✅ 登録 |
| register exam | `/events register <exam_id>` | ✅ exams_users で登録 (要 OAuth scope) |
| register 重複 | 既に登録済 id | API エラー (422 等) |
| leave 未登録 | `/events leave <id>` で未登録 | `登録していません` |
| **リマインダー** | 開始 60min 前 (±5min) を跨ぐ poll | DM `⏰ 1 時間後に開始` (1 度だけ、`event_reminders_sent` で dedupe) |
| リマインダー再起動 | DM 後に bot 再起動 → 同じ event | 再 DM 出ない (DB 永続化済) |

---

## 11. Background tasks 横断

| 機能 | トリガ | 期待 |
|---|---|---|
| Welcome | 新規メンバーがサーバー参加 | DM で `/link` 案内 + welcome ch メンション |
| レビュー通知 | 自分が evaluator/evaluated になる scale_team が新規発生 | DM 受信 (60s 以内) |
| Follow 入室通知 | フォロー中の人が新規入室 | §8 参照 |
| Event リマインダー | event/exam 開始 60min 前 | §10 参照 |

---

## 12. デモ向け推奨フロー (発表用 5 分)

1. **`/link`** でアカウント紐付け (10s)
2. **`/status <自分の login>`** で情報量を見せる (15s)
3. **`/online host_prefix:f3`** で 在校中フィルタ (10s)
4. **`/finder libft`** → Select で DM 呼出 (30s)
5. **`/find_evaluator <小さめ project>`** → 別アカウントで Accept → 募集者に DM 通知 (60s) **← 一番ウケる**
6. **`/follow add <相手の login>`** → BG task で入室通知 (待ち 60s)
7. **`/events list`** で校舎イベント一覧 (15s)
8. **`/help`** で全機能一覧 (10s)

---

## 既知の制約

- **BH 表示**: API の `blackholed_at` をそのまま出すため、intra UI の表示と乖離するケースがある (進捗段階・freeze による補正は API 値に反映されないことがある)。原因不明のため bot 側ではこれ以上補正していない。
- **`/events register` の OAuth scope**: scope `public profile projects` で動くか未検証。403 が返ったら scope 追加 + 再 link が必要。
- **slot endpoint の student 不可**: `/v2/projects/:id/slots` (403) と `/v2/teams/:id/slots` (404) で、新規レビュー予約 (`book`) は API 経由実装不可。intra UI で行う。
- **project retry**: `POST /v2/projects/:id/retry` も student で 404。intra UI で行う。
