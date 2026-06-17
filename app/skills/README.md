# app/skills

`agent.py` がこのディレクトリ配下を自動スキャンし、`SKILL.md` を持つサブディレクトリを
ADK スキルとして `SkillToolset` に登録します。スキルは下記ルールに従って
`app/skills/<skill-name>/` にコピーするだけで、再起動時に自動で読み込まれます。

## 配置ルール（`load_skill_from_dir` の制約）

```
app/skills/
└── <skill-name>/        # ★ディレクトリ名 = SKILL.md の frontmatter `name` と完全一致
    ├── SKILL.md         # ★必須（無いと読み込み対象外）
    ├── references/      # 任意
    ├── assets/          # 任意
    └── scripts/         # 任意（run_skill_script で実行可）
```

- `SKILL.md` が無いディレクトリは無視される。
- ディレクトリ名と `name` が一致しないと `ValueError` で起動に失敗する。

## SKILL.md の例

```markdown
---
name: greeting-skill
description: A friendly greeting skill that says hello to a specific person.
---

Step 1: Read the `references/hello_world.txt` file to understand how to greet.
Step 2: Return a greeting based on the reference.
```

## 動作確認

`agents-cli playground` で起動し、エージェントに `list_skills` を呼ばせて
一覧に出れば登録成功。
