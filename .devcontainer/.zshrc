# ============================================================
# 補完
# ============================================================
autoload -Uz compinit && compinit

# ============================================================
# git ブランチ表示 (zsh 標準の vcs_info を使用 / 外部ツール不要)
# ============================================================
autoload -Uz vcs_info
setopt PROMPT_SUBST                       # PROMPT 内で関数/変数を毎回展開

zstyle ':vcs_info:git:*' formats ' %F{yellow}(%b)%f'        # 通常: (branch)
zstyle ':vcs_info:git:*' actionformats ' %F{yellow}(%b|%a)%f'  # rebase 等: (branch|action)

precmd() { vcs_info }                     # プロンプト表示直前に git 状態を取得

# ============================================================
# プロンプト
#   user@host:path (branch) %
#     user = 緑, host = シアン, path = 青, branch = 黄
# ============================================================
PROMPT='%F{green}%n%f@%F{cyan}%m%f:%F{blue}%~%f${vcs_info_msg_0_} %# '

# ============================================================
# 履歴
# ============================================================
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY            # 複数ターミナル間で履歴共有
setopt HIST_IGNORE_DUPS         # 直前と同じコマンドは記録しない
setopt HIST_IGNORE_ALL_DUPS     # 履歴全体で重複を除去
setopt HIST_REDUCE_BLANKS       # 余分な空白を圧縮して保存

# ============================================================
# alias
# ============================================================
alias ll='ls -la --color=auto'
alias la='ls -A --color=auto'
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias gs='git status'
alias gb='git branch'
alias gl='git log --oneline --graph --decorate -20'
