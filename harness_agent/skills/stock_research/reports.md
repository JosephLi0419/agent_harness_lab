# Stock Research Report Format

Use this format when creating a saved stock, ETF, market, watchlist, or
investment research report.

## Filename

Default paths:

- `reports/markets/{YYYY-MM-DD}_stock_research.md`
- `reports/markets/{YYYY-MM-DD}_watchlist.md`
- `reports/markets/{YYYY-MM-DD}_market_digest.md`

Before creating a dated filename, use `get_datetime` and use the returned date
and timezone.

## Required Structure

```md
# {Ticker Or Topic} Research Report

- Date: {YYYY-MM-DD}
- Timezone: {Timezone}
- Asset or topic: {Ticker, ETF, sector, market, or portfolio topic}
- Time horizon: {User-stated horizon or Unknown}

## Executive Summary

- {Bottom-line view}
- {Primary supporting evidence}
- {Main risk or invalidation condition}

## Current Data

| Metric | Value | Source | As Of |
| --- | --- | --- | --- |
| Price | {Value or Unknown} | {Source} | {Date/time} |
| Market cap / AUM | {Value or Unknown} | {Source} | {Date/time} |
| Revenue / earnings metric | {Value or Unknown} | {Source} | {Period} |

## Business Or Exposure Overview

{Explain what the company, ETF, sector, or market exposure actually is.}

## Bull Case

- {Evidence-backed upside argument}

## Bear Case

- {Evidence-backed downside argument}

## Valuation Or Key Metrics

{Explain assumptions, comparable metrics, or why valuation is uncertain.}

## Catalysts And Watch Items

- {Upcoming earnings, filing, macro data, product event, or policy event}

## Risks And Invalidation Conditions

- {What would weaken or break the thesis}

## Practical Takeaways

- {Action framing, watchlist note, or research follow-up}

## Source Log

| Source | Date | Relevance | Notes |
| --- | --- | --- | --- |
| {Source name or path} | {Date} | {Why used} | {Important caveat} |
```

## Quality Rules

- Check current prices, filings, guidance, earnings, and news when available.
- Do not present investment opinions as certainty or guaranteed returns.
- Separate facts, assumptions, interpretation, and risk.
- Mark stale, missing, or unavailable market data clearly.
- Include invalidation conditions for thesis-style reports.
