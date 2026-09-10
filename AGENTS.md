# Agent instructions

**The instructions for this project are in [`common/CONVENTIONS.md`](common/CONVENTIONS.md)**
— the layout, the conventions a test enforces, the two-layer rule, how a course is authored,
and why each of them is the way it is.

Read that file first.

They live under `common/` rather than in this file because **no tool's filename should own
the content**. This project has three of these pointers — `CLAUDE.md`, `AGENTS.md`,
`GEMINI.md` — and one document behind them. A copy in each would be wrong within a week;
that is not a guess, it is what happened here before this folder existed.

## Skills

The same goes for what an agent can *do*. Skills are in
[`common/skills/`](common/skills/README.md), written once for every tool:

| Skill | Use it when |
|---|---|
| [`course-author`](common/skills/course-author/SKILL.md) | Writing a course from a brief, or extending, rewriting or re-generating one in `courses/`. It is the specification for the module format, the JSON schemas and the pedagogy — read it **before** writing any course content. |

Codex finds it through a stub at `.codex/skills/course-author.md`, which carries the least it needs and points
at the skill. A test fails if any of the three stubs drifts from it.
