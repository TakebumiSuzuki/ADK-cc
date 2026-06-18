# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pathlib

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.apps import App
from google.adk.environment import LocalEnvironment
from google.adk.models import Gemini
from google.adk.skills import load_skill_from_dir
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.environment import EnvironmentToolset
from google.adk.tools.load_web_page import load_web_page
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.skill_toolset import SkillToolset
from google.genai import types

_RETRY = types.HttpRetryOptions(attempts=3)

# instruction（システムプロンプト）は app/prompts/ に切り出して管理する。
# Python を触らずに文言を編集できる。
_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
_ROOT_AGENT_INSTRUCTION = (
    (_PROMPTS_DIR / "root_agent_instruction.md").read_text(encoding="utf-8").strip()
)

# google_search は他ツールと同居できない制約があるため、専用 sub-agent に分離して
# AgentTool でラップし、root_agent から呼び出す構成にする。
search_agent = Agent(
    name="web_searcher",
    model=Gemini(model="gemini-flash-latest", retry_options=_RETRY),
    instruction=(
        "You are a web search specialist. "
        "Given a search query, use Google Search to find relevant information "
        "and return a concise summary of the results."
    ),
    tools=[google_search],
)

# 汎用サブエージェント: スキルが「subagent / Agent tool で検証させろ」と指示する工程
# （narrative-to-slide-outline の QA、compose-slide-narrative の出典検証など）の委譲先。
# AgentTool でラップするため、呼び出し結果が root_agent に返る（制御は戻る）。
# 自己完結したタスクプロンプトを受け取り、./workspace のファイルを読んで検証し報告する。
general_agent = Agent(
    name="general_purpose",
    model=Gemini(model="gemini-flash-latest", retry_options=_RETRY),
    instruction=(
        "You are a general-purpose worker agent used for delegated subtasks "
        "such as QA and source verification. You receive a self-contained task "
        "prompt that includes everything you need (paths, rules, what to check). "
        "Complete the task by reading the relevant files in ./workspace and "
        "running the requested checks, then report your findings back concisely "
        "and factually. Do not invent data; if a file is missing or unreadable, "
        "say so explicitly."
    ),
    tools=[
        EnvironmentToolset(
            environment=LocalEnvironment(working_dir="./workspace"),
        ),
    ],
)

# === Google Drive (公式リモート MCP サーバー) ===
# Drive へのアクセスは Google 公式のリモート MCP サーバー経由で行う。
#   エンドポイント: https://drivemcp.googleapis.com/mcp/v1
#   公開ツール: search_files / list_recent_files / get_file_metadata /
#     get_file_permissions / read_file_content / download_file_content /
#     create_file / copy_file（create_file で本文アップロードが可能）。
# 旧構成（GoogleApiToolset は本文アップロード不可 ＋ 自作 drive_upload の二本立て）を廃し、
# ユーザー OAuth の 1 系統に統一した。
#
# 認可フロー: Gemini Enterprise が各ユーザーの OAuth 同意（scope: drive.readonly +
# drive.file）を取得し、アクセストークンをセッション state に注入する。header_provider が
# そのトークンを取り出し、MCP 呼び出しの Authorization ヘッダ（Bearer）に載せることで、
# 「話しかけている本人」として Drive を操作する（各ユーザーは自分の Drive のみ）。
#
# _DRIVE_AUTH_ID は Gemini Enterprise 側の authorizationId と一致させること
# （注入されるトークンの state キーの接頭辞になる）。URL/ID は .env で上書き可能。
_DRIVE_AUTH_ID = os.environ.get("DRIVE_AUTH_ID", "drive-auth")
_DRIVE_MCP_URL = os.environ.get(
    "DRIVE_MCP_URL", "https://drivemcp.googleapis.com/mcp/v1"
)


def _get_drive_access_token(ctx: ReadonlyContext) -> str:
    """Gemini Enterprise が state に注入した、現在のユーザーのアクセストークンを返す。

    キー名は authorizationId（_DRIVE_AUTH_ID）から派生する（例: "drive-auth_<digits>"）。
    トークン未注入の環境（ローカル開発など）では空文字を返す（呼び出しは認可エラーになる）。
    注意: 実際の state キー名は実機（Gemini Enterprise 上）で確定すること（移行計画 §5 参照）。
    """
    state = ctx.state
    items = (
        state.to_dict().items() if hasattr(state, "to_dict") else dict(state).items()
    )
    for key, value in items:
        if key.startswith(f"{_DRIVE_AUTH_ID}_"):
            return value or ""
    return ""


def _drive_auth_header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    """MCP 呼び出しごとに、現在のユーザーのトークンを Bearer ヘッダとして付与する。

    トークンが無い場合は Authorization ヘッダを付けない（空の Bearer を送らない）。
    """
    token = _get_drive_access_token(ctx)
    return {"Authorization": f"Bearer {token}"} if token else {}


drive_mcp_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url=_DRIVE_MCP_URL),
    header_provider=_drive_auth_header_provider,
    # 操作を絞りたい場合は tool_filter を指定（例: 検索・読み取り・作成のみ）:
    # tool_filter=[
    #     "search_files", "list_recent_files", "get_file_metadata",
    #     "read_file_content", "download_file_content", "create_file",
    # ],
)

# ./skills/<skill-name>/ 配下を自動スキャンし、SKILL.md を持つディレクトリを
# ADK スキルとして読み込む。スキルは後から app/skills/ にコピペするだけで、
# 再起動時に自動登録される（詳細・配置ルールは app/skills/README.md を参照）。
# 制約: ディレクトリ名は SKILL.md の frontmatter `name` と一致させること。
_SKILLS_DIR = pathlib.Path(__file__).parent / "skills"


def _load_local_skills() -> list:
    if not _SKILLS_DIR.is_dir():
        return []
    return [
        load_skill_from_dir(d)
        for d in sorted(_SKILLS_DIR.iterdir())
        if d.is_dir() and (d / "SKILL.md").is_file()
    ]


# SkillToolset は list_skills / load_skill / load_skill_resource / run_skill_script
# の汎用ツールをエージェントに提供する。スキルの発火は LLM が description を見て自律判断する。
skill_toolset = SkillToolset(skills=_load_local_skills())

root_agent = Agent(
    name="mini_claude_code",
    model=Gemini(model="gemini-flash-latest", retry_options=_RETRY),
    instruction=_ROOT_AGENT_INSTRUCTION,
    tools=[
        EnvironmentToolset(
            environment=LocalEnvironment(working_dir="./workspace"),
        ),
        load_web_page,
        AgentTool(agent=search_agent),
        AgentTool(agent=general_agent),
        drive_mcp_toolset,
        skill_toolset,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
