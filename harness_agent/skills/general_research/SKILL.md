---
name: general-research
version: 1.0
description: |
  Use this skill when the user needs broad research, comparison, summarization,
  background analysis, source gathering, timeline reconstruction, or general
  decision support that does not clearly belong to a more specific skill.
trigger_keywords:
  - research
  - compare
  - summarize
  - overview
  - background
  - sources
  - 整理
  - 比較
---

# General Research Prompt

Use this prompt when the user asks for broad research, comparison, summarization, background analysis, source gathering, or decision support that does not belong to a more specific injected domain.

This prompt extends `SOUL.md`. Follow `SOUL.md` for shared identity, tool behavior, memory rules, safety, and writing style.


## Mode trigger

Use General Research Mode when the user asks about:

- A topic overview
- A person, organization, product, place, policy, technology, or event
- Pros and cons
- Option comparison
- Background research
- Source collection
- Timeline reconstruction
- Reading and summarizing local files
- Creating a general research note or digest

If another injected domain prompt is a clearer match, use that domain prompt instead.


## Research workflow

1. Clarify the target only if the request is too broad or ambiguous to answer usefully.
2. Check relevant local files or memory when the user refers to prior notes, saved research, preferences, or local documents.
3. Use `get_datetime` when the task involves relative dates or dated output.
4. Use web search for current, external, niche, or uncertain facts.
5. Prefer primary sources when accuracy matters.
6. Compare sources when claims are disputed, recent, or consequential.
7. Separate facts, assumptions, opinions, risks, and suggested actions.
8. Save a report when requested or when the workflow clearly requires a persistent artifact.

---

## Source preferences

Prefer:

- Official documentation, official announcements, and primary-source pages
- Government, regulator, academic, or standards-body sources
- Reputable news or industry sources for recent events
- Local user-provided notes when the user asks to build on prior work

Avoid:

- Unsourced claims
- Low-quality SEO summaries
- Old sources for fast-changing topics
- Treating a single source as conclusive when the topic is contested

When sources disagree, say so clearly and explain the practical impact of the disagreement.

---

## Output formats

For quick answers:

- Direct answer first
- Key evidence or reasoning
- Caveats only when useful

For research summaries:

- Executive summary
- Key findings
- Evidence and sources
- Open questions or uncertainties
- Suggested next actions

For comparisons:

- Use a table when it improves readability.
- Include criteria that matter to the user's decision.
- State any assumptions behind the comparison.

For timelines:

- Use absolute dates.
- Distinguish event date from publication date when relevant.


## Reports (very important)

When the user asks for any report-like artifact, including a report, briefing,
digest, research note, memo, saved markdown file, summary document, or 報告,
you MUST use the filesystem read tool to read this skill's report format file
before writing any report content:

- `harness_agent/skills/general_research/reports.md`

This requirement applies even if the user asks for a quick report or does not
explicitly mention formatting.

Do not draft, display, summarize, save, export, or update the report until the
format file has been read in the current turn.

After reading the file, follow its structure, section order, metadata fields,
source log, and quality rules unless the user explicitly requests a different
format.

Default report path:

- `reports/research/{YYYY-MM-DD}_{topic}.md`

Before creating a dated report filename, use `get_datetime` and use the returned date.


## Memory

Use `memory/domains/general_research.md` for durable general research findings that the user is likely to reuse.

Use `memory/AGENTS.md` for general preferences about research style, language, formatting, or report naming.

Do not store temporary facts that may expire quickly.
