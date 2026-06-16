# Cloud Workstations で Google Drive(OAuth) 認可を通す手順（localhost ポートフォワード）

## 背景・なぜこれが必要か

ADK の playground / `adk web`（dev-ui）での OAuth 認可は、**ブラウザ内の JavaScript が `window.open()` でポップアップを開く**方式です。
そのため Cloud Workstations のプレビュー URL（`*.cloudworkstations.dev`）上では、次の理由で認可が完了しません。

1. **ポップアップがブロックされる** — `window.open()` がサーバ応答イベントのコールバック内で呼ばれ、クリック操作（user activation）に紐づかないため、ブラウザがサイレントブロックする。
2. **戻り先がゲートウェイに阻まれる** — 認可後のリダイレクト先 `…cloudworkstations.dev/dev-ui/` が Workstations の認証ゲートウェイ背後にあり、`postMessage` による完了通知が成立しない。

**解決策**: playground のポートを手元（ローカル）の `localhost` にフォワードし、`http://localhost:8000/dev-ui/` でアクセスする。
こうすると origin が `localhost` になり、ポップアップ・リダイレクト・`postMessage` がすべて素直に通る。

> ポイント: dev-ui が Google に送る callback URL（redirect_uri）は **`<ブラウザの origin>/dev-ui/`** に自動追従する。
> localhost で開けば redirect_uri も `http://localhost:8000/dev-ui/` になる。

---

## 手順

以降は playground を **8000 番**で動かす前提。別ポートなら全箇所をそのポートに読み替える。

### 1. OAuth クライアントに redirect URI を登録

Google Cloud Console → **APIs & Services → 認証情報** → `GOOGLE_OAUTH_CLIENT_ID` に対応する **OAuth 2.0 クライアント** を開く →
「**承認済みのリダイレクト URI**」に以下を追加して保存する。

```
http://localhost:8000/dev-ui/
```

- 末尾のスラッシュ込みで正確に入力する。
- 反映に数分かかることがある。

### 2. Workstation 側で playground を起動

Workstation のターミナルで、env（client_id / client_secret）を読み込んだ状態で起動する。

```bash
# GoogleApiToolset はビルド時に Drive API 仕様取得のため ADC を必要とする（未設定なら一度だけ実行）
gcloud auth application-default login

# playground 起動（通常 8000 番。起動ログでポートを確認）
agents-cli playground
```

> このとき **Workstation のプレビューでは開かない**。次のトンネル経由で localhost から開く。

### 3. ローカルマシンから接続して localhost に転送する

接続方法によって 3-A / 3-B のどちらかを選ぶ。**3-A が最も簡単**。

#### 3-A. ローカルの VS Code（デスクトップ版）で接続している場合 ← 推奨

ポートフォワードは自動。

1. VS Code の「**ポート**」パネルを開く。
2. `8000` が自動表示される。出ていなければ「**ポートの転送**」で `8000` を追加する。
3. これでローカルの `http://localhost:8000` に転送される。

gcloud コマンド不要。VS Code が裏でトンネルを張る。

#### 3-B. ブラウザ版エディタ（code-server）／その他の場合

ローカル PC（gcloud 入り）で TCP トンネルを張る。

```bash
gcloud workstations start-tcp-tunnel \
  --project=arvato-developments \
  --region=asia-southeast1 \
  --cluster=asia-cluster \
  --config=config-asia \
  workstation-takebumi \
  8000 \
  --local-host-port=localhost:8000
```


- 左の `8000` = Workstation 側ポート、`--local-host-port` の `8000` = 手元ポート。
  **手元ポートは手順 1 で登録した URI と一致**させる（ここでは両方 8000）。
- `<WORKSTATION_ID>` / `<REGION>` / `<CLUSTER_ID>` / `<CONFIG_ID>` が不明な場合の調べ方。

  Workstations のリソースは `region > cluster > config > workstation` の階層になっており、
  完全修飾名（`name` フィールド）にこの4つがすべて含まれている。

  **いちばん簡単な調べ方**（完全修飾名を一発で出す。これ1行に4つ全部入っている）:

  ```bash
  gcloud workstations list --format="value(name)"
  # 出力例:
  # projects/<PROJECT>/locations/<REGION>/workstationClusters/<CLUSTER_ID>/workstationConfigs/<CONFIG_ID>/workstations/<WORKSTATION_ID>
  ```

  > 注意: `gcloud workstations list` は **`--uri` 非対応**（`unrecognized arguments: --uri` になる）。
  > 完全修飾名は `--format="value(name)"` で取得する。

  この完全修飾名を `start-tcp-tunnel` にそのまま渡せば、cluster/config/region の個別指定は不要:

  ```bash
  gcloud workstations start-tcp-tunnel \
    projects/<PROJECT>/locations/<REGION>/workstationClusters/<CLUSTER_ID>/workstationConfigs/<CONFIG_ID>/workstations/<WORKSTATION_ID> \
    8000 \
    --local-host-port=localhost:8000
  ```

  **階層を1つずつたどる場合**（上の階層を指定して下を絞る）:

  ```bash
  gcloud workstations clusters list                                   # cluster と region を確認
  gcloud workstations configs list  --cluster=<CLUSTER_ID> --region=<REGION>
  gcloud workstations list --cluster=<CLUSTER_ID> --config=<CONFIG_ID> --region=<REGION>
  gcloud config get-value project                                     # <PROJECT_ID>
  ```

  Cloud Console の **Cloud Workstations** 画面でも各値（region / cluster / config 名）を確認できる。

- 正確なフラグは環境で異なることがあるため、初回は `gcloud workstations start-tcp-tunnel --help` で確認する。
  - `WORKSTATION` と `WORKSTATION_PORT`（VM側＝8000）は**位置引数**。
  - `--local-host-port` の既定は `localhost:0`（空きポート自動割当）。OAuth と揃えるには **`localhost:8000` を明示**する。

### 4. ローカルブラウザで認可

手元のブラウザで以下を開く。

```
http://localhost:8000/dev-ui/
```

1. エージェントに Google Drive 操作を依頼する。
2. 同意ポップアップが開く → Google アカウントで同意する。
3. `http://localhost:8000/dev-ui/` に戻ってフロー完了。

取得したトークンはセッションのクレデンシャルストア（既定では `InMemoryCredentialService` = プロセスメモリ）に保存され、
**そのプロセスが生きている間は再認可不要**になる。

---

## トラブルシュート

| 症状 | 確認・対処 |
|------|-----------|
| トンネルが別ポートになった | `http://localhost:<実ポート>/dev-ui/` を開き、その URI を OAuth クライアントに登録し直す |
| `redirect_uri_mismatch` エラー | 手順 1 の登録 URI と、実際に開いている origin + `/dev-ui/` が一致しているか確認 |
| ポップアップが出ない | DevTools の Console に `OAuth Error: Popup blocked!` が出ていないか確認。localhost で開けているか（origin を確認） |
| `adk_request_credential` の入力窓が出るだけ | 認可フローが未完了の状態。あの窓にトークンを手入力しても通らない（期待値は AuthConfig 構造体）。ポップアップを完了させる必要がある |
| Drive API 仕様取得で失敗 | 手順 2 の `gcloud auth application-default login`（ADC）を実行したか確認 |

---

## 補足

- トークンの保存先は既定で **`InMemoryCredentialService`（プロセスメモリのみ）**。playground を再起動すると消えるため、再起動後は再認可が必要。
- 永続化したい場合は、Runner 生成時に `SessionStateCredentialService` + 永続 SessionService（DB 等）を渡すなど、クレデンシャルサービスの差し替えを検討する。
