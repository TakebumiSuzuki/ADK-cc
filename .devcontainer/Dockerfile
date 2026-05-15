# node は、公式インストーラーを使ったのと同じように、/usr/local/bin/などに散在している。
FROM node:22-bookworm

# uv バイナリを Astral 公式 distroless イメージからコピー。
# /uv と /uvx は フォルダではなく単一の実行バイナリファイル。
# /usr は "Unix System Resources" の略で、OS が動作するために必要な、読み取り専用で
# 共有可能なプログラム・ライブラリ・ドキュメント類を置く場所。PATH がすでに通っている。
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# システム依存: document-skills + 基本ツール
# --no-install-recommends は推奨パッケージ(必須ではないが慣習的に一緒に入るもの)はインストールしない。
#  apt-get でインストールしたプログラムは、ほぼ /usr/ 配下（bin, lib, share に分散）に配置される。
# /usr/ は元々、全ユーザーで読み取り共有する設計の場所なので、root所有 & 他ユーザー読み取り可、で問題なし。
# apt-get で入ったコマンド（例: git, jq, pandoc など）は、典型的に 755 (rwxr-xr-x) で配置されます
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
# -p は、--parents の略。親ディレクトリも一緒に作る、もし既に存在してもエラーにしない（冪等性）
# -R は recursive で、ここでは空ディレクトリを新たに作っているので不要だが、慣習的に書かれることが多い。
# /opt はデフォルトで存在するディレクトリ。(なので本来的には -p はなくても良い)。ownerは当然 root, 権限は 755
RUN mkdir -p /opt/npm-global \
    && chown -R node:node /opt/npm-global

# PATH と NPM_CONFIG_PREFIX を /opt/npm-global に向ける
# npm install -g は NPM_CONFIG_PREFIX で指定した場所に書き込む（デフォルトは /usr/local/lib/node_modules）
# NPM_CONFIG_PREFIX の値は npm を実行する際に必ず読み込まれ、グローバルインストールの保存先として設定。
# これにより、パッケージ本体は /opt/npm-global/lib/node_modules/、実行コマンドは /opt/npm-global/bin/
ENV NPM_CONFIG_PREFIX=/opt/npm-global \
    PATH="/opt/npm-global/bin:/opt/uv-venv/bin:/home/node/.local/bin:${PATH}" \
    SHELL=/bin/zsh

# node グループに sudo 権限を付与
# /etc/sudoers.d/node という新しい設定ファイルを作り、そこに node ALL=(ALL) NOPASSWD:ALL を書き込む。
# chmod 0440 で、そのファイルを「管理者以外は書き換えもできない厳重な状態」にする
# nodeユーザーだけは特別に、パスワードなしでsudoを使えるようにしてあげる
RUN echo "node ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/node \
     && chmod 0440 /etc/sudoers.d/node

# あなたのPC（ホスト）にある zsh 用の設定ファイルを、コンテナ内の node ユーザーの所有物として、正しい場所にコピーする
COPY --chown=node:node .zshrc /home/node/.zshrc

# コンテナが起動した時のメインプロセスを実行する人
USER node

# node ユーザーとして global にインストールを実行 (/opt/npm-global)
# /opt にあるためシャドウイング(上書き消去)されず、所有者も node なので auto-update も可能！
RUN npm install -g @anthropic-ai/claude-code docx pptxgenjs

WORKDIR /workspaces/cc-dev-container