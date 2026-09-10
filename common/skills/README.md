# Skills

A skill here is a set of instructions for doing one kind of work on this project properly:
what to read first, what the contract is, and what "good" looks like. They are written for
**any** agent, which is why they live under `common/` rather than in one tool's folder.

## What there is

| Skill | Use it when |
|---|---|
| [`course-author`](course-author/SKILL.md) | Writing a course from a brief, or extending, rewriting or re-generating one in `courses/`. It is the specification for the module format, the JSON schemas and the pedagogy — read it before writing any course content, not after. |

## How each tool finds them

Each of them scans a folder of its own, in a format of its own. So each gets a **stub**: the
least a tool needs in order to find the skill, and a pointer to it. The skill itself is
written once, here.

| Tool | Stub | Shape |
|---|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md` | markdown, YAML frontmatter with `name` and `description` |
| Codex | `.codex/skills/<name>.md` | markdown, YAML frontmatter with `description`. Top-level files only — Codex does not scan subdirectories |
| Gemini CLI | `.gemini/commands/<name>.toml` | TOML with `prompt` (required) and `description`. `@{path}` injects a file, so the command carries the real skill rather than a copy of it |
| Anything reading `AGENTS.md` or `GEMINI.md` | — | those files name this one |
| A person | — | read the SKILL.md; it is prose |

**A description is not decoration.** Claude Code and Codex both read it to decide whether a
skill applies at all, so a stub whose description has drifted offers the wrong thing
confidently. `TestSkillStub` in `platform/tests/test_build.py` holds all of this: every tool
has a stub for every skill, every stub says where the skill is, the two selecting
descriptions match the skill's exactly, and the Gemini command is valid TOML that injects
the real file.

**Adding a skill:** write it in `common/skills/<name>/`, add a row to the table above, add
the three stubs, and name it in `AGENTS.md`, `GEMINI.md` and `CLAUDE.md`. The test will tell
you which of those you missed.

**Name a reference from the repo root** — `common/skills/course-author/references/x.md`, not
`references/x.md`. A relative path means two different things to a tool that opened the stub
and one that opened the skill; from the root it means one. There is a test for that too.

`platform/studio/prompts.py` is the machine-driven twin of `course-author`: Studio generates
a course unattended from the same contract this skill describes by hand. **When the module
format or a JSON schema changes, both have to change.**
