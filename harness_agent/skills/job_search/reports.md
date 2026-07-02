# Job Search Report Format

Use this format when creating a saved job search report, role shortlist, company
research note, resume-targeting report, or recurring job digest.

## Filename

Default paths:

- `reports/jobs/{YYYY-MM-DD}_latest_jobs.md`
- `reports/jobs/{YYYY-MM-DD}_company_research.md`
- `reports/jobs/{YYYY-MM-DD}_weekly_digest.md`

Before creating a dated filename, use `get_datetime` and use the returned date
and timezone.

## Required Structure

```md
# {Job Search Topic} Report

- Date: {YYYY-MM-DD}
- Timezone: {Timezone}
- Target role: {Role or Unknown}
- Target location: {Location / remote preference or Unknown}

## Executive Summary

- {Best opportunity or strongest finding}
- {Main concern or gap}
- {Recommended next action}

## Search Criteria

| Criterion | Value |
| --- | --- |
| Role type | {Value} |
| Location / remote | {Value} |
| Seniority | {Value} |
| Compensation | {Known range or Unknown} |

## Ranked Opportunities

| Rank | Role | Company | Location | Fit | Concerns | Link |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | {Role} | {Company} | {Location} | {Why it fits} | {Risk} | {URL} |

## Company Or Role Notes

### {Company Or Role}

- Summary: {What the company/team does}
- Requirements: {Key requirements}
- Fit angle: {How the user should position themselves}
- Gaps: {Missing skills, unclear requirements, or risks}

## Resume Or Interview Targeting

- Keywords to emphasize: {Keywords}
- Experience to highlight: {Examples}
- Preparation topics: {Topics}

## Next Actions

- {Apply, research further, tailor resume, contact person, skip, etc.}

## Source Log

| Source | Date Checked | Relevance | Notes |
| --- | --- | --- | --- |
| {Posting or company page} | {Date} | {Why used} | {Stale/unknown caveat} |
```

## Quality Rules

- Prefer official career pages and reputable job platforms.
- Include posting date, location, employment type, seniority, salary, and link
  when available.
- Mark stale, sponsored, duplicate, vague, or likely expired postings.
- Do not invent salary, visa, remote, or hiring details.
- Rank roles according to known user preferences first.
