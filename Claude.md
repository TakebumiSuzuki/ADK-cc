## 0. プロジェクト概要

Google ADK（Agent Development Kit）を使って構築する **自律型コーディングエージェント**。
ファイル読み書き・シェル実行・Web 検索・Web ページ取得などのツールを組み合わせ、ユーザーのタスクを反復的に完遂する。
エントリーポイントは `app/agent.py`（`root_agent`）。開発は `agents-cli playground` / `agents-cli run` で行い、本番は Cloud Run 等へデプロイする。

---

## 0-1. 開発環境で使えるツール・ライブラリ

> `.devcontainer/Dockerfile` に基づく。

### システムコマンド（apt）
| コマンド | 用途 |
|---------|------|
| `git` | バージョン管理 |
| `jq` | JSON 整形・クエリ |
| `zsh` | シェル |
| `nano` | テキストエディタ |
| `pandoc` | ドキュメント変換（Markdown / DOCX / HTML 等） |
| `libreoffice` | Office ファイル操作（CLI 経由） |
| `poppler-utils` | PDF → 画像変換（`pdftoppm` 等） |
| `qpdf` | PDF 分割・結合・変換 |
| `tesseract-ocr` / `tesseract-ocr-jpn` | OCR（日本語対応） |
| `gcc` / `libc6-dev` | C コンパイル（Python 拡張ビルド用） |
| `fonts-noto-cjk` 等 | 日本語フォント |

### Python ライブラリ（`/opt/uv-venv`）
| パッケージ | 用途 |
|-----------|------|
| `pypdf` / `pdfplumber` | PDF テキスト抽出 |
| `reportlab` | PDF 生成 |
| `pandas` | データ処理 |
| `openpyxl` | Excel 読み書き |
| `pytesseract` | OCR（Python バインディング） |
| `pdf2image` | PDF → 画像変換 |
| `markitdown[pptx]` | PowerPoint → Markdown 変換 |
| `Pillow` | 画像処理 |
| `defusedxml` | 安全な XML パース |

### Node.js グローバルコマンド（`/opt/npm-global`）
| コマンド | 用途 |
|---------|------|
| `claude` | Claude Code CLI |
| `docx` | DOCX 操作（npm: docx） |
| `pptxgenjs` | PPTX 生成（npm: pptxgenjs） |

### Python 実行
- **`uv run python`** を使う（`python` 直接呼び出し不可）
- 依存追加後は `uv sync` を実行

---

## 0-2. ADK 開発ガイドライン

> 詳細は @AGENTS.md を参照（agents-cli のワークフロー・コマンド・コーディングルールを記述）。

主要コマンド早見表：

| コマンド | 用途 |
|---------|------|
| `agents-cli run "..."` | 1ショット動作確認（最速） |
| `agents-cli playground` | Web UI でインタラクティブテスト |
| `agents-cli eval run` | 評価（品質の定量検証） |
| `agents-cli lint` | ruff による lint + フォーマットチェック |
| `agents-cli deploy` | デプロイ（**要ユーザー承認**） |

---

## 1. 事実確認とツール利用 (Verification & Tool Usage)
- **AIの記憶ベースの実装禁止**: API名、関数シグネチャ、設定値、CLIフラグなど、正確性が必須のコードや文字列はAIの記憶に頼らず、必ず一次情報から取得してください。
- **情報収集フロー**:
  1. ライブラリやSDKの仕様は、まずMCPサーバー `context7` を使用して取得してください。
  2. 上記で解決できない場合や、最新の製品仕様・ニュースについては `WebSearch` 等を使用して現状を確認してください。
- **未検証の明示**: 外部ツールを駆使しても確証が得られなかった場合は、勝手な推測でコードを書かず、必ず「未検証（推測）である」旨を明記してください。

## 2. 質問と意思決定 (Clarification & Decision Making)
- **曖昧な指示の確認**: ユーザーの指示が複数に解釈できる場合や矛盾がある場合は、推測で進めず `AskUserQuestion` で確認してください。**ただし、既存のソースコードやファイルを調べれば判明することは、質問する前にまずコードを読んで自己解決してください。**
- **設計の選択**: データベース設計（スキーマ・インデックス）、ライブラリ選定、アーキテクチャの方向性など、複数の選択肢やトレードオフが存在する場合は独断で決定せず、`AskUserQuestion` で選択肢を提示してユーザーの判断を仰いでください。

## 3. 安全性と破壊的操作 (Security & Critical Operations)
- **不可逆操作前の許可取得**: 以下の操作を実行する前は、必ず `AskUserQuestion` でユーザーの許可を得てください。
  - `git push --force`, `git reset --hard`, ブランチの削除などの履歴改変
  - データベースのドロップ、マイグレーションの実行、本番環境への変更
  - `rm -rf` 等によるファイルやディレクトリの大規模な削除