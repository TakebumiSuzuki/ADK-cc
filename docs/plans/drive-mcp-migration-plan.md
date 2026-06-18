# Google Drive MCP 移行計画

**ブランチ**: `feature/mcp-server`
**作成日**: 2026-06-18
**対象**: `app/agent.py` の `drive_toolset`（`GoogleApiToolset`）＋自作 `drive_upload_tool` を、**Google 公式 Drive リモート MCP サーバー**へ移行する。

---

## 1. 目的とゴール

- **アップロード必須**：成果物（`.md`/`.html` 等）をユーザー自身の Google Drive に書き出せること。
- **各ユーザーが自分の Drive のみ**を読み書き（他人の Drive は操作しない／無人運用なし）。
- 現状の「`GoogleApiToolset`（中身アップロード不可）＋自作 `drive_upload`（ADC）」の二本立て・二重認証を解消し、**1 系統（ユーザー OAuth）に統一**する。
- デプロイ先は既存構成どおり **Vertex AI Agent Engine**、ユーザー窓口は **Gemini Enterprise（旧 Agentspace）**。

### 非ゴール（今回やらない）
- 共有ドライブ（Shared Drive）対応（既知バグあり。My Drive 用途では不要）。
- サービスアカウント／ドメイン委任による無人運用。

---

## 2. 現状（As-Is）

`app/agent.py`:
- `drive_toolset = GoogleApiToolset(api_name="drive", ...)` … 検索・メタデータ操作は可、**本文アップロード不可**。OAuth はツール内にハードコードの authorization_code フロー。
- `drive_upload_tool = FunctionTool(drive_upload)` … ADC（`google.auth.default`, scope `drive.file`）で本文アップロードを補完。`except Exception` で握り潰し（後述の 2.0 リトライ注意点に該当）。

デプロイ構成（確認済み）:
- `app/agent_runtime_app.py` … `AgentEngineApp(AdkApp)`。Artifacts は既に **`GcsArtifactService`**（`LOGS_BUCKET_NAME` 有り）／無ければ InMemory。
- `agents-cli-manifest.yaml` … `deployment_target: agent_runtime`。
- `deployment_metadata.json` … 未デプロイ（`remote_agent_runtime_id: None`）。
- バージョン: **google-adk 2.0.0b1（ベータ）／ agents-cli 0.4.0**。

---

## 3. 移行後（To-Be）アーキテクチャ

```
[ユーザー10人]
   │ chat
   ▼
Gemini Enterprise（出来合いUI・OAuth同意・トークン管理）
   │  各ユーザーのアクセストークンを session state に注入
   ▼
Agent Engine（root_agent / AgentEngineApp）
   │  header_provider が state からトークンを取り、Bearer ヘッダで付与
   ▼
Drive MCP（https://drivemcp.googleapis.com/mcp/v1） … 本人として読み書き・アップロード
```

---

## 4. 確定した技術事実（裏採り済み）

### 4-1. Drive 公式リモート MCP サーバー
- **エンドポイント**: `https://drivemcp.googleapis.com/mcp/v1`（HTTP トランスポート）
- **必要スコープ**: `https://www.googleapis.com/auth/drive.readonly` ＋ `https://www.googleapis.com/auth/drive.file`
- **公開ツール（8種）**: `search_files`, `list_recent_files`, `get_file_metadata`, `get_file_permissions`, `read_file_content`, `download_file_content`, `create_file`, `copy_file`
  - **`create_file` で本文アップロード可**（`drive.file` スコープで書き込み）。→ 自作 `drive_upload` が不要になる。
- **前提**: GCP プロジェクトで **Drive API と Drive MCP API を有効化**／OAuth 同意画面（ブランディング）設定／OAuth 2.0 ウェブクライアント作成。
- 出典: developers.google.com/workspace/drive/api/guides/configure-mcp-server

### 4-2. ADK `McpToolset`（ローカル実体で確認＝最も確実）
`google.adk.tools.mcp_tool.mcp_toolset.McpToolset.__init__` シグネチャ（2.0.0b1）:
```
connection_params: StdioServerParameters | StdioConnectionParams | SseConnectionParams | StreamableHTTPConnectionParams
tool_filter, tool_name_prefix, auth_scheme, auth_credential,
header_provider: Optional[Callable[[ReadonlyContext], Dict[str, str]]],
require_confirmation, ...
```
- **`StreamableHTTPConnectionParams`** でリモート HTTP MCP に接続可。
- **`header_provider`** が使える（引数は `ReadonlyContext`。`.state` 読み取り可）→ ここで per-user トークンを Bearer 付与。
- 注意: **`credential_key` は 2.0.0b1 には無い**（2.1.0 で追加）。header_provider 方式は b1 でも利用可。

### 4-3. Gemini Enterprise への登録 & OAuth 認可（REST API）
- **OAuth クライアントのリダイレクト URI** に Vertex のものを登録:
  - `https://vertexaisearch.cloud.google.com/oauth-redirect`
  - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
- **認可リソース作成**（一回・エージェント単位）:
  ```
  POST .../v1alpha/projects/PROJECT_NUMBER/locations/LOCATION/authorizations?authorizationId=AUTH_ID
  { "serverSideOauth2": { clientId, clientSecret, authorizationUri, tokenUri } }
  ```
  - `authorizationUri` テンプレート: `https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...oauth.html&scope=<drive.readonly+drive.file>&access_type=offline&prompt=consent`
- **エージェント登録時に認可を紐付け**: `authorizationConfig.toolAuthorizations: ["projects/.../authorizations/AUTH_ID"]`
- 出典: docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent

### 4-4. per-user トークンの受け取り（コード側）
Gemini Enterprise が注入したトークンを `state` から取り、`header_provider` で MCP へ渡す（コードラボのパターン）:
```python
def _get_access_token(ctx) -> str:
    state = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else ctx.state
    for k in state:                       # キーは AUTH_ID から派生（例 "drive-auth_<digits>"）
        if k.startswith(f"{AUTH_ID}_"):
            return state[k]
    return ""

def auth_header_provider(ctx) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token(ctx)}"}
```
- 出典: codelabs.developers.google.com/ge-gws-agents ほか

---

## 5. 未確定・要検証項目（実装時に一次情報で確定）

1. **`state` の正確なキー名**：資料により `AUTH_ID_<digits>` パターン or 設定キー方式の差。実機の state ダンプで確定する。
2. **Drive MCP のトランスポート詳細**：`StreamableHTTPConnectionParams` か `SseConnectionParams` か（ドキュメントは "HTTP" 表記のみ）。接続時に確定。
3. **header_provider に渡る `ReadonlyContext` から注入トークンが読めるか**：ToolContext 前提のコードラボ例との差異を実機確認。
4. **Drive MCP と Gemini Enterprise の認可の二重性**：GE 注入トークン（Bearer）だけで `drivemcp.googleapis.com` が受理するか、MCP 側 OAuth と整合するかを結合テストで確認。
5. **`create_file` の引数仕様**（本文をどう渡すか／ファイルサイズ上限）。
6. **ローカル開発での代替検証手段**（GE が無い環境でのトークン注入の擬似化）。

---

## 6. 移行ステップ（フェーズ）

### Phase 0: 準備
- [x] 本ブランチ `feature/mcp-server` で作業（済）。
- [ ] GCP プロジェクトで **Drive API ＋ Drive MCP API を有効化**。
- [ ] OAuth 同意画面の設定、**OAuth 2.0 ウェブクライアント**作成（dev 用／本番用の 2 つ。リダイレクト URI に Vertex の 2 URL）。

### Phase 1: 依存・バージョン
- [x] **google-adk 2.2.0 / agents-cli 0.5.0 へ更新済み。**（注: `scaffold upgrade` ではなく `pyproject.toml` 直接更新＋`uv sync` で実施。`google-adk[mcp]` extra を追加し `mcp 1.28.0` 導入。`McpToolset` は `header_provider`＋`credential_key` 両対応を確認。）
- [x] `uv sync` 済。**pytest は test extra 未整備のため ephemeral 実行**（`uv run --with pytest`）→ unit 通過。integration はモデル/ADC 認証情報がこの環境に無く未完（コード起因ではない）。
- [x] モデルは **`gemini-flash-latest` のまま**（デフォルト変更に追従しない）。

### Phase 2: コード変更（`app/agent.py`）
- [x] `drive_toolset`（GoogleApiToolset）と `drive_upload_tool`（FunctionTool）を**削除**。
- [x] `McpToolset(connection_params=StreamableHTTPConnectionParams(url="https://drivemcp.googleapis.com/mcp/v1"), header_provider=_drive_auth_header_provider)` を追加し、`root_agent.tools` に登録。
- [x] `_get_drive_access_token` / `_drive_auth_header_provider` を実装（§4-4）。
- [x] 不要になった import（`GoogleApiToolset`, `FunctionTool`, `mimetypes`）を整理。さらに `app/prompts/root_agent_instruction.md` の旧ツール記述（`drive_upload`/`drive_files_list`）を MCP ツール名（`search_files`/`read_file_content`/`create_file`）に更新。Phase 1 で延命用に足した `google-api-python-client` も撤去。
  - **副次的改善**: GoogleApiToolset 撤去により、`app.agent` の import が ADC 不要になった（McpToolset は遅延接続）。
- [ ] `agents-cli lint` 通過。（**未**: 0.5.0 が要求する `lint` extra が未定義のため lint 実行不可。scaffold 整備が前提。）

### Phase 3: ローカル検証
- [ ] `agents-cli run` / `playground` でツール一覧に Drive MCP ツールが出ることを確認。（**この環境では困難**: モデル認証情報が無く playground 起動不可。後述。）
- [ ] トークン注入が無いローカルでは認可エラーになる前提。**ロジック部分**を中心に確認（§5-6 の代替手段を検討）。
  - 済み: import レベルで `McpToolset` が `root_agent.tools` に登録されることは確認済み（tool 型一覧で検証）。

### Phase 4: デプロイ＆結合テスト（本命の認可フロー検証）
- [ ] `agents-cli deploy`（**要ユーザー承認**）で Agent Engine へ。
- [ ] Gemini Enterprise に**認可リソース作成**（AUTH_ID, scope=drive.readonly+drive.file）＋**エージェント登録**（§4-3）。
- [ ] テストユーザーで「Authorize」→ 同意 → 検索・読み取り・**アップロード（create_file）**を確認。
- [ ] state のキー名を実測し、`_get_access_token` を確定（§5-1）。

### Phase 5: 仕上げ
- [ ] 10 ユーザーで各自の Drive のみ操作できることを確認（他人の Drive に触れないこと）。
- [ ] ドキュメント更新（README / CLAUDE.md の Drive 周りの記述）。
- [ ] PR 作成（main へ）。

---

## 7. コード変更スケッチ（`app/agent.py`）

> 実装フェーズで確定。現時点は方向性のスケッチ（キー名・トランスポートは要検証）。

```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

AUTH_ID = "drive-auth"  # Gemini Enterprise の authorizationId と一致させる

def _get_access_token(ctx) -> str:
    state = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else ctx.state
    for k in state:
        if k.startswith(f"{AUTH_ID}_"):
            return state[k]
    return ""

def auth_header_provider(ctx) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token(ctx)}"}

drive_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://drivemcp.googleapis.com/mcp/v1",
    ),
    header_provider=auth_header_provider,
    # tool_filter=[...]  # 必要なら read/search/create に絞る
)

# root_agent.tools: drive_toolset / drive_upload_tool を削除し drive_mcp を追加
```

---

## 8. リスク & ロールバック

| リスク | 対応 |
|---|---|
| GE のトークン注入キー名が想定と違う | Phase 4 で実測し確定。`_get_access_token` を調整 |
| 2.0.0b1→2.2.0 で API/セッション DB 非互換 | Phase 1 で pytest/eval 検証。問題あれば 2.x 内の安定版で固定 |
| `drive_upload` 内 `except Exception` のリトライ阻害（2.0 仕様） | MCP 移行で当該関数は削除されるため解消 |
| Drive MCP のトランスポート不一致 | SSE/Streamable を切替えて接続確認 |
| ロールバック | 本ブランチを破棄すれば `main`（GoogleApiToolset 構成）に戻る。マージ前に検証完了を必須とする |

---

## 9. 出典
- Drive MCP 設定: https://developers.google.com/workspace/drive/api/guides/configure-mcp-server
- Gemini Enterprise 登録/認可: https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent
- Workspace MCP 構成: https://developers.google.com/workspace/guides/configure-mcp-servers
- ADK×OAuth×Gemini Enterprise: https://fmind.medium.com/powering-up-your-agent-in-production-with-adk-oauth-and-gemini-enterprise-a52b0716fcba
- Codelab (GE×Workspace): https://codelabs.developers.google.com/ge-gws-agents
- McpToolset 実体: ローカル `google/adk/tools/mcp_tool/mcp_toolset.py`（v2.0.0b1）
