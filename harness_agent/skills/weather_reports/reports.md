# Weather Report Format

Use this format when creating a saved daily weather report, travel weather note,
outdoor planning report, or multi-location weather comparison.

## Filename

Default paths:

- `reports/weather/{YYYY-MM-DD}_daily_weather.md`
- `reports/weather/{YYYY-MM-DD}_travel_weather.md`

Before creating a dated filename, use `get_datetime` and use the returned date
and timezone.

## Required Structure

```md
# {Location} Weather Report

- Date: {YYYY-MM-DD}
- Timezone: {Timezone}
- Location: {Location}
- Forecast period: {Date/time window}
- Activity or purpose: {Activity, travel plan, or Unknown}

## Executive Summary

- {Practical bottom line}
- {Main weather risk}
- {Best time window or preparation advice}

## Forecast

| Period | Temperature | Rain / storm risk | Wind | Air quality | Notes |
| --- | --- | --- | --- | --- | --- |
| {Time window} | {Range} | {Risk} | {Wind} | {AQI or Unknown} | {Practical note} |

## Practical Impact

- Comfort: {Assessment}
- Outdoor suitability: {Assessment}
- Travel impact: {Assessment}

## Preparation

- {What to wear, bring, reschedule, or monitor}

## Risks And Uncertainty

- {Severe weather, forecast confidence, missing data, or official alert caveat}

## Source Log

| Source | Date Checked | Relevance | Notes |
| --- | --- | --- | --- |
| {Weather source} | {Date/time} | {Why used} | {Caveat} |
```

## Quality Rules

- Always state location, date, and forecast period clearly.
- Treat severe weather, typhoons, heavy rain, and air quality as uncertainty-
  sensitive; encourage checking official alerts when relevant.
- Do not fabricate weather data.
- Translate weather data into practical impact for the user's activity.
- Mark unavailable forecast details as `Unknown`.
