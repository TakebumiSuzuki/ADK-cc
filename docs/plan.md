# Mini Claude Code Agent — 実装計画 (rev.2)

> 目的: Google ADK v2 beta を使い、Claude Code のように **単一エージェントが ReAct ループでファイル作成・編集・シェル実行・Web取得を自律的に行う** プロトタイプを構築する。

---

## 1. 調査結果サマリー（一次情報、2026‑05‑15 取得）

### 1.1 Gemini Enterprise Agent Platform
- 旧称 Vertex AI Agent Builder。2026‑04‑22 GA
- Vertex AI Agent Engine → **Agent Runtime**、Vertex AI Search → **Agent Platform Search** に名称変更
- 開発フレームワーク = **ADK (Agent Development Kit)**（Python/TS/Go/Java）

### 1.2 ADK Python のバージョン状況（**重要・更新**）

| ライン | 最新 | リリース日 | 用途 |
|---|---|---|---|
| 安定版 (v1系) | **v1.33.0** | 2026‑05‑08 | 本番向け。実は v2 beta より日付が新しい |
| プレリリース (v2系) | **v2.0.0b1** | 2026‑04‑22 | グラフ Workflow API のβ。新しい beta はまだ無し |

- 公式 install: `pip install google-adk --pre`（v2 系を取る場合）
- uv: `uv add 'google-adk>=2.0.0b1' --prerelease=allow`（**未検証**、ダメなら `.venv/bin/pip` でフォールバック）
- 「ユーザー指示は v2 beta」のため本計画は **v2.0.0b1** を採用

### 1.3 v2.0 で何が変わったか（誤解しやすいポイント）

- **sub-agent / AgentTool / transfer_to_agent は v0.1.0 から公式サポート**（v2 の新規機能ではない）
- v2.0 の真の新機能 = **Workflow API**：グラフベース、明示 ReAct ノード、HITL resume、状態管理改善
- ただし Workflow API は **pre‑GA、opt‑in 推奨**（skill 警告あり）
- **本計画では Workflow API は使わず、v1 互換の `LlmAgent + tools` パターン**で実装する
  - LLM 自身が ReAct（推論 → ツール呼出 → 観察 → 次の推論）のループを回す
  - これがそのまま Claude Code 風の自律動作になる

### 1.4 Claude Code 相当ツールの ADK 対応

| Claude Code | ADK | 提供形態 | 備考 |
|---|---|---|---|
| Read / Write / Edit | `ReadFile` / `WriteFile` / `EditFile` | `EnvironmentToolset` (Google 公式・Experimental) | **ADK v1.29+** |
| Bash | `Execute` | 同上 | |
| WebFetch | `load_web_page` | `google.adk.tools.load_web_page` | 制約なし、併用OK |
| WebSearch | `google_search` | `google.adk.tools` (Gemini Grounding) | **同居制約あり** → sub-agent+AgentTool で回避 |
| Grep / Glob | — | カスタム `FunctionTool` で別途実装可（今回は最小構成のため省略） | |

`EnvironmentToolset(LocalEnvironment(working_dir=..., env_vars=...))` 1つで read/write/edit/bash がそろう。

### 1.5 Gemini モデル名（**重要・新規確認**）

`gemini-3.0-flash-latest` は **存在しない**（命名規則違い）。2026‑05 時点の実在モデル:

| モデルID | ステータス | リリース |
|---|---|---|
| `gemini-3-flash` | Preview | 2026‑04‑22 |
| `gemini-3.1-pro` | Preview | — |
| `gemini-3.1-flash-lite` | **GA** | 2026‑05‑07 |
| `gemini-flash-latest` | hot-swap alias | 常時最新Flash |

採用方針: **`gemini-flash-latest` をデフォルト**（開発時のシンプルさ重視）。本番運用するなら明示版（`gemini-3-flash` など）に切替。ユーザーが「Gemini 3 系に固定」を希望する場合は `gemini-3-flash` を採用。

### 1.6 agents-cli の状態
- `google-agents-cli` v0.1.3 が dev dependency 済、`uv run agents-cli` で動作確認済み
- skill 7 種が `.claude/skills/` に展開済み
- `[tool.agents-cli]` セクションは未設定 → `scaffold enhance` で追加

### 1.7 既存ファイルの保護方針（**新規**）
- プロジェクトルートに既存の `Claude.md`（事実確認・質問・安全性ルール）が存在
- scaffold が `CLAUDE.md` を生成すると **Linux FS では別ファイル扱い**だが、Claude Code が両方読んでしまう可能性
- 安全策: scaffold の `--agent-guidance-filename` に **`AGENTS.md` を指定**してガイダンスファイルを別名に逃がす
  - これで既存 `Claude.md` は完全に温存
  - 生成された `AGENTS.md` には scaffold が必要とする ADK 開発規約が入る（Claude Code は AGENTS.md も読む慣行）

---

## 2. アーキテクチャ

```
                 ┌─────────────────────────────────────┐
                 │  root_agent (LlmAgent, v1互換API)   │
                 │  model: gemini-flash-latest         │
                 │  instruction: Claude Code風         │
                 └────────────┬────────────────────────┘
                              │ tools=[...]
        ┌─────────────────────┼────────────────────────────┐
        │                     │                            │
   ┌────▼─────────────┐  ┌────▼──────────┐  ┌──────────────▼──────┐
   │ EnvironmentToolset│  │ load_web_page │  │ search_agent_tool   │
   │  (LocalEnv:       │  │  (URL→本文)   │  │   = AgentTool(       │
   │   working_dir=    │  │               │  │      Agent(          │
   │   ./workspace)    │  │               │  │        tools=        │
   │                   │  │               │  │        [google_search]│
   │ - ReadFile        │  │               │  │      )               │
   │ - WriteFile       │  │               │  │   )                  │
   │ - EditFile        │  │               │  └──────────────────────┘
   │ - Execute (bash)  │  │               │
   └───────────────────┘  └───────────────┘
        ReAct ループは LLM が tools を連続呼出することで自動成立
```

実行: `GOOGLE_API_KEY=xxx uv run agents-cli run "..."` または `uv run agents-cli playground`

---

## 3. ファイル構成（予定）

```
cc-dev-container/
├── docs/
│   └── plan.md              ← 本ドキュメント
├── app/                     ← scaffold enhance が生成
│   ├── __init__.py
│   ├── agent.py             ← root_agent + search sub-agent を実装
│   └── ...
├── workspace/               ← LocalEnvironment.working_dir (ランタイム生成)
├── pyproject.toml           ← [tool.agents-cli] 追加 + google-adk>=2.0.0b1
├── uv.lock
├── main.py                  ← 不要なら削除、または agent 起動スクリプトとして書き換え
├── Claude.md                ← **温存**（既存内容を保護）
├── AGENTS.md                ← scaffold が新規生成（ADK開発規約）
└── ...
```

---

## 4. 実行ステップ

### Step 0: 事前バックアップ
```bash
git add -A && git commit -m "WIP: snapshot before agents-cli scaffold enhance"
```
これで enhance が何かを破壊しても復元できる。

### Step 1: enhance でプロトタイプ構成を整える
```bash
uv run agents-cli scaffold enhance . \
  --deployment-target none \
  --prototype \
  --agent-directory app \
  --agent-guidance-filename AGENTS.md \
  --google-api-key
```
- `--agent-guidance-filename AGENTS.md`: **既存 Claude.md と衝突しない別名に逃がす**
- `--google-api-key`: AI Studio APIキー認証モード
- `--prototype` + `--deployment-target none`: CI/CD・Terraform・デプロイ設定なし

> 実行前に `... --dry-run` で差分プレビュー推奨。`pyproject.toml` がどう書き換わるか確認してから本実行。

### Step 2: ADK 2.0 beta へ切替
scaffold が ADK 1.x 依存で `pyproject.toml` を書く可能性が高いため、v2.0.0b1 に差し替え:
```bash
uv add 'google-adk>=2.0.0b1' --prerelease=allow
uv sync
uv run python -c "import google.adk; print(google.adk.__version__)"
```
ダメだった場合のフォールバック:
```bash
.venv/bin/pip install --upgrade --pre 'google-adk>=2.0.0b1'
```

### Step 3: `app/agent.py` を実装
最小構成のスケッチ（API正確性は実装時に context7 で再確認）:
```python
from google.adk.agents import Agent
from google.adk.environment import LocalEnvironment
from google.adk.tools.environment import EnvironmentToolset
from google.adk.tools.load_web_page import load_web_page
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import google_search

MODEL = "gemini-flash-latest"  # 必要なら "gemini-3-flash" に切替

# Built-in tool 同居制約を回避する Web 検索 sub-agent
search_agent = Agent(
    name="web_searcher",
    model=MODEL,
    instruction="ユーザーから検索クエリを受け取り、Google検索で結果を要約して返してください。",
    tools=[google_search],
)

root_agent = Agent(
    name="mini_claude_code",
    model=MODEL,
    instruction=(
        "あなたは Claude Code 風の自律エージェントです。"
        "ユーザーのタスクが完了するまで、必要なツールを連続的に呼び出してください。"
        "- ファイル操作は EnvironmentToolset (ReadFile/WriteFile/EditFile/Execute) を使う\n"
        "- URLからの本文取得は load_web_page\n"
        "- Web検索は web_searcher サブエージェントを呼び出す\n"
        "作業ディレクトリは ./workspace に閉じてください。"
    ),
    tools=[
        EnvironmentToolset(
            environment=LocalEnvironment(working_dir="./workspace"),
        ),
        load_web_page,
        AgentTool(agent=search_agent),
    ],
)
```

### Step 4: API キーをコマンドで渡して動作確認
ユーザー希望どおり `.env` 不要、起動時に環境変数で渡す:
```bash
mkdir -p workspace

GOOGLE_API_KEY=xxxx GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  uv run agents-cli run "workspace内にhello.txtを作って 'hello from ADK v2' と書いてください"

GOOGLE_API_KEY=xxxx GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  uv run agents-cli run "https://example.com を取得して内容を要約してください"

GOOGLE_API_KEY=xxxx GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  uv run agents-cli run "Pythonの最新バージョンをweb検索で調べてください"

GOOGLE_API_KEY=xxxx GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  uv run agents-cli playground   # ブラウザでインタラクティブ確認
```

頻繁に使うなら shell の export か、direnv の `.envrc`（gitignore）を検討。

---

## 5. 未検証事項（CLAUDE.md ルールに従い明示）

| 項目 | 状態 | 対策 |
|---|---|---|
| `uv add google-adk --prerelease=allow` が v2.0.0b1 を解決するか | **未検証** | pip フォールバック案あり |
| v2.0.0b1 で `EnvironmentToolset` / `LocalEnvironment` の import パスが v1.29 系と互換か | **未検証** | 実装時に `python -c "from google.adk.tools.environment import EnvironmentToolset"` で確認 |
| `scaffold enhance` の既存 pyproject.toml への影響 | **未検証** | Step 0 で git commit + `--dry-run` |
| `--prototype` と `--deployment-target none` の組み合わせ | **未検証** | `agents-cli scaffold enhance --help` で再確認 |
| `agents-cli run` での agent モジュール解決ルール | **未検証** | scaffold 生成 `pyproject.toml [tool.agents-cli]` を確認 |
| `gemini-3-flash` を直接モデルIDとして使えるか（公式IDの正確な形） | **未検証** | デフォルトは `gemini-flash-latest`、必要時 `gemini-3-flash` を試す |
| `EnvironmentToolset` の Experimental ステータスによる API 変更リスク | **既知** | 動作確認後にAPI不変か再確認 |

---

## 6. リスクとフォールバック

- **enhance が既存ファイルを破壊**: Step 0 の git commit + `--dry-run` + ガイダンスファイル名を `AGENTS.md` に逃がす
- **ADK 2.0 beta のAPIが Document と差異**: v2.0.0b1 の `llms.txt`（context7 経由）または `import` 時の inspect で確認
- **google_search の sub-agent 方式がADK 2.0で動かない**: `bypass_multi_tools_limit=True` 直結を試す
- **EnvironmentToolset.Execute が想定外に強力**: working_dir で物理隔離 + instruction で危険コマンド禁止のガード
- **モデルID指定エラー（404）**: `gemini-flash-latest` に戻す、または Vertex 経由で `client.models.list()` を実行して確定IDを取得

---

## 7. 次のアクション

1. 本計画を確認
2. 承認後、Step 0（git commit）→ Step 1（scaffold enhance --dry-run）の順で実行
3. dry-run の差分を見ていただいて、問題なければ本実行へ
