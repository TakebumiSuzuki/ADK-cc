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

import mimetypes
import os
import pathlib

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.environment import LocalEnvironment
from google.adk.models import Gemini
from google.adk.skills import load_skill_from_dir
from google.adk.tools import FunctionTool, google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.environment import EnvironmentToolset
from google.adk.tools.google_api_tool import GoogleApiToolset
from google.adk.tools.load_web_page import load_web_page
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

# Google Drive: ファイルの検索・読み書き・共有を OAuth（ユーザー同意）で動的にアクセスする。
# files.list で検索、get/export で取得、create/update でアップロード・更新、copy/delete も可能。
# 認証情報は .env から読む（リポジトリに秘密情報を書かない）。
# 注意: GoogleApiToolset は生成時に Drive API 仕様を取得するため Application Default
# Credentials を必要とする。ローカルで playground / import する前に
# `gcloud auth application-default login` を実行しておくこと。
drive_toolset = GoogleApiToolset(
    api_name="drive",
    api_version="v3",
    client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
    # 操作を絞りたい場合は tool_filter を指定（例: 読み書き＋検索のみ）:
    # tool_filter=[
    #     "drive_files_list", "drive_files_get", "drive_files_export",
    #     "drive_files_create", "drive_files_update", "drive_files_copy",
    #     "drive_files_delete",
    # ],
)

# drive_upload: ./workspace 内のテキスト/Markdown ファイルを、開発者本人の Google Drive に
# アップロードする。drive_toolset（自動生成ツール）は本文（メディア）を載せられないため、
# 書き出しはこの専用 FunctionTool が担う。バイト列は LLM コンテキストを経由しない。
# 認証は ADC（Application Default Credentials）。事前に下記を実行しておくこと:
#   gcloud auth application-default login \
#     --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.file
_DRIVE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def drive_upload(filename: str, drive_name: str = "", folder_id: str = "") -> dict:
    """Upload a text/Markdown file from ./workspace to the user's Google Drive.

    Use this to save a generated artifact (e.g. a narrative `.md`) back to Drive.
    The file must already exist inside ./workspace (write it with WriteFile first).
    Only text-based files are supported; binary uploads are not handled here.

    Args:
        filename: Path of the file to upload, relative to ./workspace
            (e.g. "narrative.md"). Must stay inside ./workspace.
        drive_name: Optional name for the file on Drive. Defaults to the
            source file's name.
        folder_id: Optional Drive folder ID to upload into. Defaults to the
            user's My Drive root.

    Returns:
        On success: {"id", "name", "webViewLink"} of the created Drive file.
        On failure: {"error", "error_code"}.
    """
    workspace = pathlib.Path("./workspace").resolve()
    src = (workspace / filename).resolve()
    if not src.is_relative_to(workspace):
        return {
            "error": "filename must stay inside ./workspace.",
            "error_code": "OUTSIDE_WORKSPACE",
        }
    if not src.is_file():
        return {"error": f"File not found: {filename}", "error_code": "NOT_FOUND"}

    try:
        import google.auth
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds, _ = google.auth.default(scopes=_DRIVE_UPLOAD_SCOPES)
        service = build("drive", "v3", credentials=creds)

        mime_type = mimetypes.guess_type(src.name)[0] or "text/markdown"
        body = {"name": drive_name or src.name}
        if folder_id:
            body["parents"] = [folder_id]
        media = MediaFileUpload(str(src), mimetype=mime_type, resumable=False)
        created = (
            service.files()
            .create(body=body, media_body=media, fields="id, name, webViewLink")
            .execute()
        )
        return {
            "id": created.get("id"),
            "name": created.get("name"),
            "webViewLink": created.get("webViewLink"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "error_code": "UPLOAD_FAILED"}


drive_upload_tool = FunctionTool(func=drive_upload)

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
        drive_toolset,
        drive_upload_tool,
        skill_toolset,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
