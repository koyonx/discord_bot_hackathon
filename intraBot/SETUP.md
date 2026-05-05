# intraBot セットアップガイド

42 Tokyo の intra API を叩く Discord bot のセットアップ手順。**上から順に書かれているコマンド / URL / 入力値をそのままコピペすれば `.env` まで完成する** ことをゴールにしている。

順序が重要 (前のステップで取得した値を次で使う) なので **飛ばさず上から順番にやる** こと。

---

## 0. 用意するもの

- 42 Tokyo の intra アカウント (普段ログインしているやつ)
- Discord アカウント (テストサーバーへの **Manage Server** 以上の権限を持っていること)
- macOS / Linux ターミナル
- Docker Desktop (起動済み)

```bash
# 既に入っているものは飛ばして OK (`which docker` 等で確認)
command -v docker        >/dev/null || brew install --cask docker     # Docker Desktop
command -v ngrok         >/dev/null || brew install ngrok             # 永続トンネル
command -v jq            >/dev/null || brew install jq                # 動作確認 step で使う (任意)
```

Docker Desktop が初めて入った場合 / まだ起動していない場合は GUI を立ち上げる:

```bash
open -a Docker            # 🐳 アイコンが出て "Docker Desktop is running" になるまで待つ (~30s)
docker ps                 # 空のテーブルが出れば daemon 起動 OK
```

---

## STEP 1. ngrok で **永続 HTTPS URL** を発行する

42 OAuth2 は **HTTPS の Redirect URI** しか受け付けない。さらに Redirect URI を毎回 42 アプリ側に登録し直すのは面倒なので、**一度取れば変わらない URL** を ngrok の無料 static domain で確保する。再起動しても同じ URL が再利用できる。

### 1-1. ngrok アカウントを作る

<https://dashboard.ngrok.com/signup> を開いて **GitHub または Google でサインアップ** (無料)。

### 1-2. 永続ドメインを発行する

サインイン後:

1. 左サイドバー **Domains** を開く: <https://dashboard.ngrok.com/domains>
2. ページ右上の **+ New Domain** または **Create Domain** を押す
3. 確認ダイアログ (free tier) → **Continue** → 自動でドメインが払い出される
4. 表示されたドメイン (例: `intrabot-1234.ngrok-free.app`) をコピーしてメモする。以後 **`<NGROK_DOMAIN>`** と書く

> 無料アカウントでは static domain は **1 つだけ** 持てる。それで十分。**この URL は今後変わらない**。

### 1-3. authtoken をコピーする

別タブで <https://dashboard.ngrok.com/get-started/your-authtoken> を開く → **Your Authtoken** 欄に表示されている文字列をコピー。以後 `<NGROK_AUTHTOKEN>` と書く。

### 1-4. ngrok をインストールして authtoken を登録 (このマシンで 1 度だけ)

```bash
brew install ngrok
ngrok config add-authtoken <NGROK_AUTHTOKEN>
```

`add-authtoken` は `~/.config/ngrok/ngrok.yml` に保存されるので、同じマシンでは 1 度だけ実行すれば OK。

### 1-5. ターミナル A でトンネルを起動 (このターミナルは閉じない)

```bash
ngrok http --url=<NGROK_DOMAIN> 4242
```

具体例:

```bash
ngrok http --url=intrabot-1234.ngrok-free.app 4242
```

以下の行が出れば成功:

```
Forwarding   https://intrabot-1234.ngrok-free.app -> http://localhost:4242
```

以後 **`<TUNNEL_URL>`** = `https://<NGROK_DOMAIN>` (例: `https://intrabot-1234.ngrok-free.app`) として参照する。

> 💡 **`--url=<NGROK_DOMAIN>` は必須**。これを付けないと毎回ランダム URL になってしまい固定化の意味が無くなる。スクリプト化したいなら `intraBot/Makefile` の `make tunnel` ターゲットから呼ぶようにする (実装側で用意予定)。

---

## STEP 2. 42 OAuth2 アプリを登録する

### 2-1. ブラウザで以下を開く (intra にログインした状態で)

<https://profile.intra.42.fr/oauth/applications/new>

### 2-2. フォームに以下を入力する

| フィールド | 入れる値 |
|---|---|
| **Name** | `intraBot-dev` (任意。何でも良い) |
| **Image** | 空のまま OK |
| **Redirect URI** | `<TUNNEL_URL>/callback` ← STEP 1-2 でメモした URL の末尾に `/callback` を付けたもの。例: `https://intrabot-1234.ngrok-free.app/callback` |
| **Website** | 空のまま OK |
| **Scopes** | 下の 3 つを ON (UI ラベル基準) |

#### Scopes (チェックする 3 つ)

| UI ラベル (画面の表記) | 対応する scope 名 | 用途 |
|---|---|---|
| ☑ Access the user public data | `public` | 既定でチェック済。ユーザー公開情報・projects_users・locations・scale_teams の読み取り |
| ☑ **Manage teams, slots and all projects related stuff** | `projects` | `/slot add` `/slot del` に必須 |
| ☑ **Manage user data** | `profile` | `/v2/me` で本人 login を確実に取るため |

以下はチェック **不要**:

- ☐ Manage media related stuff (`tig`)
- ☐ Manage community services
- ☐ Manage topics and messages (`forum`)

### 2-3. ページ最下部の **Submit** ボタンを押す

### 2-4. 発行された `UID` と `SECRET` をメモする

Submit するとアプリ詳細ページに飛ぶ。以下の 2 つの値が表示されているのでテキストエディタにコピーする。

- **UID** … `s-s4t-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` のような 80 文字前後の文字列
- **SECRET** … 同様の文字列。**SECRET は再表示できない** ので必ずここでコピーする。なくしたら同じページの "Roll" ボタンで再発行が必要。

以後、これらを `<INTRA_UID>` `<INTRA_SECRET>` と書く。

### 2-5. (動作確認 / 任意) トークンが取れることを確認

ターミナル B (新しいタブ) で:

```bash
curl -s -X POST 'https://api.intra.42.fr/oauth/token' \
  -d 'grant_type=client_credentials' \
  -d 'client_id=<INTRA_UID>' \
  -d 'client_secret=<INTRA_SECRET>' | jq
```

`access_token` が返ってくれば登録は成功。

---

## STEP 3. Discord アプリと Bot を作る

### 3-1. ブラウザで以下を開く

<https://discord.com/developers/applications>

### 3-2. 右上 **New Application** ボタンを押す

ダイアログに `intraBot` と入力 → 規約に同意 → **Create**。

### 3-3. Application ID をメモする

遷移後の画面の **General Information** タブにある **APPLICATION ID** の下の数字 (19 桁前後) をコピー。以後 `<DISCORD_APP_ID>` と書く。

### 3-4. Bot Token を発行する

1. 左サイドバー **Bot** をクリック
2. **TOKEN** セクションの **Reset Token** ボタン → 確認ダイアログで **Yes, do it!**
3. 表示されたトークン文字列 (3 ブロックに分かれた長い文字列) をコピー。以後 `<DISCORD_TOKEN>` と書く
4. **再表示できない** ので必ずここでコピー

### 3-5. Privileged Intents を設定する

同じ **Bot** ページの下方 **Privileged Gateway Intents** セクションで:

- ☐ Presence Intent → **OFF のまま**
- ☑ **Server Members Intent** → **ON にする** (welcome フローで必須)
- ☐ Message Content Intent → **OFF のまま**

ON にしたら下の **Save Changes** を必ず押す。

### 3-6. 招待 URL を生成して bot をテストサーバーに入れる

1. 左サイドバー **OAuth2** をクリック (Bot の下にある)
2. 中央の **OAuth2 URL Generator** セクションで:
   - **SCOPES**: 以下 2 つにチェック
     - ☑ `bot`
     - ☑ `applications.commands`
3. その下の **BOT PERMISSIONS** で以下にチェック:
   - ☑ View Channel
   - ☑ Send Messages
   - ☑ Send Messages in Threads
   - ☑ Embed Links
   - ☑ Read Message History
   - ☑ Use Application Commands (= スラッシュコマンド)
4. ページ最下部に生成された **GENERATED URL** をコピー → 別タブで開く
5. ドロップダウンで **テスト用サーバー** を選択 → **認証** ボタン → CAPTCHA → **Authorize**
6. テストサーバーに `intraBot` メンバーが追加されていることを確認

---

## STEP 4. テスト用 Discord サーバーを準備する

### 4-1. Developer Mode を ON にする

Discord クライアントで:

1. 左下の歯車アイコン (User Settings) を開く
2. 左メニュー **App Settings → Advanced**
3. **Developer Mode** のトグルを ON

これで右クリックメニューに "Copy ID" 系の項目が出るようになる。

### 4-2. サーバー ID を取得する

左サイドバーで **テストサーバーのアイコンを右クリック** → **Copy Server ID**。

→ クリップボードに 19 桁前後の数字が入る。これが `<DISCORD_GUILD_ID>`。

### 4-3. welcome 用チャンネルを準備する

新規メンバー参加時に "`/link` してね" と通知するためのチャンネル。

1. 既存に `#welcome` などが無ければ、テストサーバーで右クリック → **Create Channel** → Text チャンネルとして `welcome` を作成
2. 作ったチャンネルを **右クリック → Copy Channel ID** → これが `<DISCORD_WELCOME_CHANNEL_ID>`
3. チャンネルの設定 (歯車アイコン) → **Permissions** で `intraBot` ロールに以下が ✓ になっていることを確認:
   - View Channel
   - Send Messages
   - Embed Links

> bot にロールが自動で付かない場合は **Server Settings → Members** で intraBot を選択し、`@intraBot` ロール (招待で自動作成される) を割り当てる、または上記権限を `@everyone` に開放しておけば動く。

---

## STEP 5. `.env` を作る

プロジェクトルートで:

```bash
cd intraBot
cp .env.example .env
```

エディタで `intraBot/.env` を開いて、以下のように **STEP 1〜4 でメモした値** で埋める。

```dotenv
# ===== Discord =====
DISCORD_TOKEN=<DISCORD_TOKEN>                          # STEP 3-4
DISCORD_APP_ID=<DISCORD_APP_ID>                        # STEP 3-3
DISCORD_GUILD_ID=<DISCORD_GUILD_ID>                    # STEP 4-2
DISCORD_WELCOME_CHANNEL_ID=<DISCORD_WELCOME_CHANNEL_ID> # STEP 4-3

# ===== 42 intra OAuth2 =====
INTRA_UID=<INTRA_UID>                                  # STEP 2-4
INTRA_SECRET=<INTRA_SECRET>                            # STEP 2-4
INTRA_REDIRECT_URI=<TUNNEL_URL>/callback               # STEP 1-2 + /callback (STEP 2-2 と同一文字列)

# ===== 動作設定 (基本そのままで OK) =====
INTRA_CAMPUS_NAME=Tokyo
INTRA_API_BASE=https://api.intra.42.fr
NOTIFY_POLL_SECONDS=60
DB_PATH=/data/intrabot.sqlite
OAUTH_CALLBACK_HOST=0.0.0.0
OAUTH_CALLBACK_PORT=4242
```

> `.env` は **絶対にコミットしない**。`.gitignore` に追加済み。

---

## STEP 6. 起動

ターミナル A (ngrok) は起動したまま、ターミナル B で:

```bash
cd intraBot
make build
make up
make logs
```

ログに以下が出れば起動成功:

```
intraBot | [info] resolved campus_id=26 (Tokyo)
intraBot | [info] OAuth callback server listening on 0.0.0.0:4242
intraBot | [info] Discord bot logged in as intraBot#1234
intraBot | [info] slash commands synced to guild <DISCORD_GUILD_ID>
```

---

## STEP 7. 動作確認

### 7-1. `/link` で 42 アカウントを紐付け

1. テストサーバーの任意のチャンネルで `/link` と打つ
2. bot が DM で以下のような URL を送ってくる:

   ```
   👋 42 アカウントの紐付けはこちら:
   https://api.intra.42.fr/oauth/authorize?client_id=<INTRA_UID>&redirect_uri=<TUNNEL_URL>%2Fcallback&response_type=code&scope=public+profile+projects&state=xxxx
   ```

3. URL を踏む → 42 にログイン (普段使ってるアカウントで OK) → **Authorize** ボタン
4. ngrok 経由で `/callback` に飛び、bot DM に **`✅ 紐付け完了 (login: <あなたの42 login>)`** が届けば成功

### 7-2. 各コマンドのスモークテスト

| コマンド | 期待挙動 |
|---|---|
| `/status <他人のlogin>` | embed で 座席 / レベル / 合格課題 / 進行中 / eval point / BH / freeze が出る |
| `/slot list` | 自分の slot 一覧 (空なら「登録なし」) |
| `/slot add 2026-05-10T14:00 60` | intra の Find a peer ページに 14:00〜15:00 の slot が出る |
| `/slot del <slot_id>` | 指定 slot が intra から消える |
| `/finder libft` | libft 合格者かつ現在校舎にいる cadet が embed 表示される |

### 7-3. eval 通知

intra で誰かが自分のレビューに登録 (またはこちらが登録) されると、約 60 秒以内 (`NOTIFY_POLL_SECONDS`) に bot DM が来ることを確認。

---

## トラブルシューティング

| 症状 | 確認すること |
|---|---|
| `/link` の URL を踏んだ後 `redirect_uri_mismatch` | STEP 2-2 の Redirect URI と `.env` の `INTRA_REDIRECT_URI` が **末尾の `/callback` まで完全一致** しているか。`http` / `https` 違いも NG |
| `/link` の URL を踏んでも `/callback` がタイムアウト | ターミナル A の ngrok が落ちていないか / `--url=<NGROK_DOMAIN>` 付きで起動しているか確認 |
| `/status` などが "未紐付け" エラー | 先に `/link` で 42 アカウントを紐付ける |
| slash command が出ない | 起動ログに `slash commands synced to guild ...` があるか。無ければ `DISCORD_GUILD_ID` の値が間違っている可能性大 |
| bot がオフライン表示のまま | `DISCORD_TOKEN` が正しいか / `make logs` でエラーを確認 |
| 42 API が 401 / 403 連発 | STEP 2-2 の Scope が `public profile projects` の 3 つチェック済みか。足りない場合はアプリページで scope を追加してから再度 `/link` |
| `/slot add` が 422 | API の制約: **15 分単位 / 過去日 NG / 既存 slot と重複 NG**。エラーメッセージは DM にそのまま流れる |
| ngrok 起動時に違う URL (Forwarding 行が `xxx.ngrok-free.app` の別ドメイン) が出る | `--url=<NGROK_DOMAIN>` を付け忘れている。**必ず** `ngrok http --url=<NGROK_DOMAIN> 4242` で起動する |
| `ERR_NGROK_3200` / `tunnel ... not found` | <https://dashboard.ngrok.com/domains> で `<NGROK_DOMAIN>` がまだ存在するか確認。誤って削除してしまった場合は再作成すれば同じ名前で取り直せることもあるが、別ドメインになったら STEP 2-2 の Redirect URI と `.env` を更新 |

---

## (参考) 各種エンドポイントと値の早見表

| 名前 | 値 |
|---|---|
| 42 OAuth2 authorize | `https://api.intra.42.fr/oauth/authorize` |
| 42 OAuth2 token | `https://api.intra.42.fr/oauth/token` |
| 42 API base | `https://api.intra.42.fr/v2` |
| 42 アプリ管理ページ | `https://profile.intra.42.fr/oauth/applications` |
| Discord Developer Portal | `https://discord.com/developers/applications` |
| Tokyo の campus_id | `26` (起動時に bot が API で再解決するので `.env` には不要) |
| OAuth callback (ローカル) | `http://localhost:4242/callback` |
| OAuth callback (公開) | `<TUNNEL_URL>/callback` |
| 必要な 42 scope | `public profile projects` |
| 必要な Discord scope | `bot applications.commands` |
| 必要な Discord 権限 | View Channel / Send Messages / Send Messages in Threads / Embed Links / Read Message History / Use Application Commands |

---

## 後で追加予定 (このセットアップでは不要)

- freeze 申請コマンド (`/freeze request`)
- グローバル反映の slash command (本番デプロイ時に切り替え)
- Fly.io / Railway へのデプロイ手順
- ngrok 以外のトンネル選択肢 (cloudflared named tunnel / Tailscale Funnel) への切り替え手順
