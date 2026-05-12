FROM node:22-bookworm

# uv バイナリを Astral 公式 distroless イメージからコピー
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# システム依存: document-skills + 基本ツール
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

# uvが管理するPython本体を /opt/uv-python に配置（デフォルトの /root/.local/share/uv は node から読めない）
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
RUN uv python install 3.13 \
     && uv venv /opt/skills-venv --python 3.13 \
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
     && chown -R node:node /opt/skills-venv /opt/uv-python

# ==========================================
# npm のグローバルインストール先をボリューム( /home/node )の外である
# /opt/npm-global に作成し、所有者を node に変更しておく。
# ==========================================
RUN mkdir -p /opt/npm-global \
    && chown -R node:node /opt/npm-global

# ==========================================
# PATH と NPM_CONFIG_PREFIX を /opt/npm-global に向ける
# ==========================================
ENV NPM_CONFIG_PREFIX=/opt/npm-global \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    PATH="/opt/npm-global/bin:/opt/skills-venv/bin:/home/node/.local/bin:${PATH}" \
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