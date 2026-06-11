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

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.environment import LocalEnvironment
from google.adk.models import Gemini
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.environment import EnvironmentToolset
from google.adk.tools.google_api_tool import GoogleApiToolset
from google.adk.tools.load_web_page import load_web_page
from google.genai import types

_RETRY = types.HttpRetryOptions(attempts=3)

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

root_agent = Agent(
    name="mini_claude_code",
    model=Gemini(model="gemini-flash-latest", retry_options=_RETRY),
    instruction=(
        "You are an autonomous coding agent, similar to Claude Code. "
        "Complete user tasks by iteratively reasoning and calling tools — "
        "keep looping until the task is fully done.\n\n"
        "Available tools:\n"
        "- ReadFile: read an existing file in ./workspace\n"
        "- WriteFile: create a new file in ./workspace\n"
        "- EditFile: edit an existing file in ./workspace\n"
        "- Execute: run shell commands (working directory is ./workspace)\n"
        "- load_web_page: fetch and return the text content of a URL\n"
        "- web_searcher: delegate Google Search queries to a sub-agent\n"
        "- Google Drive tools: search files (drive_files_list with a `q` query), "
        "read/export them, and create/update/copy/delete files on the user's Drive\n\n"
        "Rules:\n"
        "- All file operations must stay inside the ./workspace directory.\n"
        "- Never execute destructive commands (e.g. rm -rf /, format drives).\n"
        "- Think step by step before each action.\n"
        "- Report what you did and what you found after each tool call."
    ),
    tools=[
        EnvironmentToolset(
            environment=LocalEnvironment(working_dir="./workspace"),
        ),
        load_web_page,
        AgentTool(agent=search_agent),
        drive_toolset,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
