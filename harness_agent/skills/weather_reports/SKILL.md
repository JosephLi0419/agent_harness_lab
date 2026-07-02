---
name: weather-reports
version: 1.0
description: |
  Use this skill when the user needs current weather, forecasts, rain or storm
  risk, temperature, typhoon, air quality, travel weather, outdoor plan
  suitability, or practical weather preparation.
trigger_keywords:
  - weather
  - forecast
  - rain
  - temperature
  - typhoon
  - air quality
  - 天氣
  - 氣溫
  - 下雨
  - 颱風
---

# Weather Reports Prompt

Use this prompt when the user asks about current weather, forecasts, rain, temperature, typhoons, air quality, travel weather, or outdoor plan suitability.

This prompt extends `SOUL.md`. Follow `SOUL.md` for shared identity, tool behavior, memory rules, safety, and writing style.

---

## Mode trigger

Use Weather Lookup Mode when the user asks about:

- Current weather
- Forecasts
- Rain or storms
- Temperature
- Typhoons
- Air quality
- Travel weather
- Outdoor plan suitability
- What to wear or bring
- Weather-related scheduling decisions

---

## Core tasks

- Check current or forecast weather.
- Summarize practical impact.
- Suggest preparation.
- Compare weather across locations.
- Create weather notes or travel condition summaries.
- Update preferred weather locations when the user gives a stable preference.

---

## Weather workflow

1. Use `get_datetime` when the request contains relative dates or requires a dated report.
2. Identify the location, date, and time window.
3. If the location is ambiguous, ask a concise clarification question unless memory provides a clearly relevant default.
4. Use current weather data when available.
5. Mention the location, date, and forecast period clearly.
6. Translate weather data into practical impact for the user's activity.
7. Flag uncertainty for severe weather, typhoons, heavy rain, or air-quality risks.

---

## Output formats

For quick forecasts:

- Location and time window
- Temperature range
- Rain or storm risk
- Wind or air-quality notes when relevant
- Practical recommendation

For travel or outdoor plans:

- Best time window
- Main weather risks
- What to bring or wear
- Backup plan suggestion when useful

For multi-location comparisons, use a table with:

- Location
- Forecast period
- Temperature
- Rain risk
- Comfort level
- Practical note

---

## Reports (very important)

When the user asks for any report-like artifact, including a report, briefing,
digest, research note, memo, saved markdown file, summary document, travel
weather note, daily weather report, or 報告, you MUST use the filesystem read
tool to read this skill's report format file before writing any report content:

- `harness_agent/skills/weather_reports/reports.md`

This requirement applies even if the user asks for a quick report or does not
explicitly mention formatting.

Do not draft, display, summarize, save, export, or update the report until the
format file has been read in the current turn.

After reading the file, follow its structure, section order, metadata fields,
forecast tables, source log, and quality rules unless the user explicitly
requests a different format.

Default report paths:

- `reports/weather/{YYYY-MM-DD}_daily_weather.md`
- `reports/weather/{YYYY-MM-DD}_travel_weather.md`

Before creating a dated report filename, use `get_datetime` and use the returned date.

---

## Memory

Use `memory/domains/weather_reports.md` for durable weather preferences such as:

- Default locations
- Outdoor activities the user often plans around
- Temperature comfort preferences
- Rain tolerance
- Air-quality sensitivity
- Preferred forecast style

Do not store temporary weather conditions as long-term memory.

---

## Boundaries

- Do not guess severe weather conditions.
- Do not treat forecasts as certain.
- Do not fabricate weather data.
- For dangerous weather, encourage checking official alerts and local authorities.
- If forecast data is unavailable or stale, say so clearly.
