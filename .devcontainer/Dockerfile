FROM node:22-bookworm

# uv バイナリを Astral 公式 distroless イメージからコピー。
# /uv と /uvx は フォルダではなく単一の実行バイナリファイル。
# /usr は "Unix System Resources" の略で、OS が動作するために必要な、読み取り専用で
# 共有可能なプログラム・ライブラリ・ドキュメント類を置く場所。PATH がすでに通っている。
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# システム依存: document-skills + 基本ツール
# --no-install-recommends は「推奨パッケージ(必須ではないが慣習的に一緒に入るもの)は
# インストールしない」というオプションで、イメージサイズを抑えるための定番テクニック
#  apt-get でインストールしたプログラムは、ほぼ /usr/ 配下（bin, lib, share に分散）に配置される。
# /usr/ は元々、全ユーザーで読み取り共有する設計の場所なので、root所有 & 他ユーザー読み取り可、で問題なし。
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
     nano \
     && rm -rf /var/lib/apt/lists/*

# uvが管理するPython本体を /opt/uv-python にインストール。
#（デフォルトは /root/.local/share/uv だが、これでは 運用中に、nodeユーザー から読めない）
# /rootは慣習的に他ユーザーから完全に隔離される設定になっているので、いじらず、/optにインストールしている。
# /opt は、OSのパッケージ管理体系から外れた、追加でインストールするソフトウェア一式を置く場所。
# 通常、/opt/<ベンダー名>/<製品名>/　のようになる。
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python

RUN uv python install 3.13 \
     && uv venv /opt/uv-venv --python 3.13 \
     && uv pip install --python /opt/uv-venv/bin/python \
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
     && chown -R node:node /opt/uv-venv /opt/uv-python

# npm のグローバルインストール先をボリューム( /home/node )の外である
# /opt/npm-global に作成し、所有者を node に変更しておく。
RUN mkdir -p /opt/npm-global \
    && chown -R node:node /opt/npm-global

# ==========================================
# PATH と NPM_CONFIG_PREFIX を /opt/npm-global に向ける
# npm install -g は NPM_CONFIG_PREFIX で指定した場所に書き込む（デフォルトは /usr/local/lib/node_modules）
# ==========================================
ENV NPM_CONFIG_PREFIX=/opt/npm-global \
    PATH="/opt/npm-global/bin:/opt/uv-venv/bin:/home/node/.local/bin:${PATH}" \
    SHELL=/bin/zsh

# node グループに sudo 権限を付与
RUN echo "node ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/node \
     && chmod 0440 /etc/sudoers.d/node

# zsh 設定
COPY --chown=node:node .zshrc /home/node/.zshrc

# コンテナが起動した時のメインプロセスを実行する人
USER node

# ==========================================
# node ユーザーとして /opt/npm-global にインストールを実行。
# /opt にあるためシャドウイング(上書き消去)されず、所有者も node なので auto-update も可能！
# ==========================================
RUN npm install -g @anthropic-ai/claude-code docx pptxgenjs

WORKDIR /workspaces/cc-dev-container