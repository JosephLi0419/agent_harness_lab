# General Research Report Format

Use this format when creating a saved research report, briefing, comparison note,
timeline, or decision-support document.

## Filename

Default path:

- `reports/research/{YYYY-MM-DD}_{topic}.md`

Before creating a dated filename, use `get_datetime` and use the returned date
and timezone.

## Required Structure

```md
# {Topic} Research Report

- Date: {YYYY-MM-DD}
- Timezone: {Timezone}
- Prepared for: {User or audience, if known}
- Scope: {One-sentence scope}

## Executive Summary

- {Most important finding}
- {Second most important finding}
- {Recommended action or practical implication, if applicable}

## Background

{Concise context needed to understand the topic.}

## Key Findings

1. **{Finding}**
   - Evidence: {Source or observation}
   - Implication: {Why it matters}

## Analysis

{Synthesize the evidence. Separate facts, assumptions, and interpretation.}

## Risks And Uncertainties

- {Known limitation, conflicting source, stale data, or open question}

## Recommendations Or Next Steps

- {Actionable next step}

## Source Log

| Source | Date | Relevance | Notes |
| --- | --- | --- | --- |
| {Source name or path} | {Date} | {Why used} | {Important caveat} |
```

## Quality Rules

- Use absolute dates.
- Mark unknown or unavailable information as `Unknown`; do not invent it.
- Prefer primary sources and local user-provided materials when available.
- Use tables only when they make comparison or scanning easier.
- Keep conclusions proportional to the evidence.
