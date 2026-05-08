FROM node:22-bookworm

# uv バイナリを Astral 公式 distroless イメージからコピー（curl 不要、再現性確保）
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# システム依存: document-skills (pdf/docx/pptx/xlsx) + 基本ツール
RUN apt-get update && apt-get install -y --no-install-recommends \
     libreoffice \
     poppler-utils \
     qpdf \
     pandoc \
     tesseract-ocr \
     tesseract-ocr-jpn \
     gcc \
     libc6-dev \
     fonts-noto-cjk \
     fonts-noto-cjk-extra \
     fonts-liberation \
     git \
     ca-certificates \
     sudo \
     procps \
     less \
     jq \
     zsh \
     && rm -rf /var/lib/apt/lists/*


# Claude Code CLI + document-skills 用 Node パッケージ
# node:22-bookworm では、npm の prefix が /usr/local に設定されている。なので、-g でインストール
# すると /usr/local/lib/node_modules/ にパッケージが置かれ、実行ファイルは /usr/local/bin/ となる。
# /usr/local/bin/は、デフォルトで PATH が通っているので、問題なく動く
RUN npm install -g @anthropic-ai/claude-code docx pptxgenjs


# uvが管理する専用ディレクトリ（ /root/.local/share/uv/python/）にビルド済みのPythonバイナリを配置
RUN uv python install 3.13 \
     # uv venvは、uv が提供するコマンド。"uv 管理下の Python 3.13 を使って仮想環境を作れ"という意味。
     # これにより、/opt/skills-venv/bin/python　という Python 3.13　へのシンボリックリンクができる。
     && uv venv /opt/skills-venv --python 3.13 \
     # ここの uv pip　も、uvが独自に提供するコマンド。裏で python -m pip を呼び出しているわけではない。
     # 使い勝手を良くするために、あえて pip install というサブコマンド名を借用している。
     && uv pip install --python /opt/skills-venv/bin/python \
     pypdf \
     pdfplumber \
     reportlab \
     pandas \
     openpyxl \
     pytesseract \
     pdf2image \
     "markitdown[pptx]" \
     Pillow \
     defusedxml \
     # -R は recursive、node:node は FROM node:22-bookworm で作られているユーザーとグループを表す。
     # この時点では root（superuser）が作成したので、ownerがrootとなっている。それを node に変更する
     && chown -R node:node /opt/skills-venv


# PATH を ENV で恒久設定（非対話シェル・サブプロセスから参照できるよう zshrc 追記ではなくここで）
# このイメージには、一般ユーザーとして node が作られていて、/home/node/ も存在している。
#  /home/node/.local/bin については、non-root ユーザー（node）が後からインストールした時の実行ファイル
#　置き場。将来的に node ユーザーが追加ツールを入れたときに、そのまま動くように先回りで通している。
ENV PATH="/opt/skills-venv/bin:/home/node/.local/bin:${PATH}" \
     SHELL=/bin/zsh

# node グループに sudo 権限を付与（開発時の apt install 等で使う場合に備えて）
RUN echo "node ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/node \
     && chmod 0440 /etc/sudoers.d/node

# zsh 設定 (プロンプト / git ブランチ表示 / 履歴 / alias)
# COPY は root 権限で実行されるので USER 切替の前に置く。--chown で node 所有に。
COPY --chown=node:node .zshrc /home/node/.zshrc

# コンテナが起動した時のメインプロセス（PID 1）を実行する人
# 例えば、CMD ["flask", "run"] と書かれていた場合、このプロセス（PID 1）を誰が実行するかを決める
USER node

# コンテナ内で新しく生まれるプロセス(pid 1)のデフォルト初期位置を指定する設定
WORKDIR /workspaces/cc-dev-container
