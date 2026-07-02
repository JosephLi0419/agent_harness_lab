# Agent Harness Lab

Agent Harness Lab is a local CLI agent built with LangGraph. It is designed to
route user requests into different domain skills, use tools when needed, and
keep lightweight local memory across sessions.

## What This Agent Does

The agent currently focuses on four practical workflows:

- General research: summarize topics, compare options, collect sources, build
  background notes, and create structured research summaries.
- Stock research: research stocks, ETFs, earnings, market news, valuation,
  bull and bear cases, risks, catalysts, and watch items.
- Job search: search and compare roles, summarize job requirements, research
  companies, prepare interview or resume angles, and create job digests.
- Weather reports: check forecasts, compare locations, explain outdoor or
  travel impact, and suggest what to prepare.

The agent chooses a skill automatically from your message, or you can select
one manually with CLI options or chat commands.

## Features

- LangGraph-based chat loop with a command-line interface.
- LLM-based skill routing using each skill prompt's front matter.
- Azure OpenAI and local Ollama provider support.
- Local memory files for reusable preferences and research context.
- Tool support for filesystem access, web search, webpage extraction, and
  datetime lookup.
- Middleware for skill injection, memory injection, todo tracking, context
  compaction, tool-call cleanup, and approval before risky file writes.

## Requirements

- Python 3.14 or newer
- `uv`
- One LLM provider:
  - Azure OpenAI, or
  - Ollama running locally

## Quick Start

Clone the repo and install dependencies:

```bash
git clone https://github.com/JosephLi0419/agent_harness_lab.git
cd agent_harness_lab
uv sync
```

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit `.env` for either Azure OpenAI or Ollama.

Start an interactive chat:

```bash
uv run agent-harness-lab chat
```

Ask one question and exit:

```bash
uv run agent-harness-lab ask "Summarize this project"
```

## LLM Setup

### Azure OpenAI

Add these values to `.env`:

```env
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_API_KEY=<your-azure-openai-api-key>
```

Run with Azure OpenAI:

```bash
uv run agent-harness-lab chat --provider azure
```

### Ollama

Start Ollama and make sure the model exists locally:

```bash
ollama pull qwen3.6:35b-a3b-q8_0
```

Add optional overrides to `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.6:35b-a3b-q8_0
```

Run with Ollama:

```bash
uv run agent-harness-lab chat --provider ollama
```

## CLI Usage

Show available commands:

```bash
uv run agent-harness-lab --help
```

Start a chat:

```bash
uv run agent-harness-lab chat
```

Ask a single prompt:

```bash
uv run agent-harness-lab ask "Compare this week's market headlines"
```

List available skills:

```bash
uv run agent-harness-lab skills
```

Show config, memory, and skill paths:

```bash
uv run agent-harness-lab config
```

Useful runtime options:

```bash
--provider azure|ollama
--domain stock_research
--skill stock_research
--thread-id my-session
--no-memory
--no-compact
```

Examples:

```bash
uv run agent-harness-lab chat --domain stock_research
uv run agent-harness-lab ask --skill weather_reports "Is Taipei good for running tomorrow?"
uv run agent-harness-lab chat --thread-id research-session-1
```

Inside chat, you can switch skills:

```text
/skill stock
/domain weather
```

## Built-In Skills

### `general_research`

Use this for broad research, comparisons, summaries, source gathering,
background analysis, timelines, and decision support.

Example:

```bash
uv run agent-harness-lab ask --skill general_research "Compare LangGraph and CrewAI"
```

### `stock_research`

Use this for stocks, ETFs, market news, earnings, valuation, catalysts, risks,
portfolio questions, and investment research notes.

Example:

```bash
uv run agent-harness-lab ask --skill stock_research "Analyze NVDA's current bull and bear case"
```

### `job_search`

Use this for job postings, role comparison, company research, resume targeting,
interview preparation, salary research, and job-market digests.

Example:

```bash
uv run agent-harness-lab ask --skill job_search "Find AI product manager roles and rank them"
```

### `weather_reports`

Use this for current weather, forecasts, rain risk, typhoons, travel weather,
outdoor planning, and what to wear or bring.

Example:

```bash
uv run agent-harness-lab ask --skill weather_reports "Will Taipei be good for running tomorrow morning?"
```

## How Skills Work

Skills are prompt packages stored under:

```text
harness_agent/skills/<skill_id>/
  SKILL.md
  reports.md
```

`SKILL.md` starts with a fixed YAML-style front matter block. The LLM router
only reads this metadata while selecting a skill. After a skill is selected,
the agent loads and injects the full `SKILL.md`.

```md
---
name: skill-name-lowercase
version: 1.0
description: |
  Use this skill when the user needs a specific task or workflow. Explain both
  what the skill does and when it should be selected.
trigger_keywords:
  - optional keyword
  - optional phrase
---
```

`name` must be lowercase letters, numbers, and hyphens only, up to 64
characters. `trigger_keywords` is optional and is passed to the LLM router as
extra routing context, not used for deterministic keyword matching.

The `<skill_id>` folder name is still used internally for state, memory, and
prompt injection. The LLM router does not see that folder id; it chooses from
the `SKILL.md` front matter names.

`reports.md` defines the report template for that skill. When a skill needs to
generate a saved report, its `SKILL.md` should instruct the agent to consult the
matching `reports.md` before writing the report.

Skill selection priority:

```text
1. /skill or /domain command in the latest user message
2. state["pinned_skills"]
3. state["active_domain"]
4. state["active_skills"] when no messages are present
5. state["skill_ids"]
6. LLM routing from the latest user message and each SKILL.md front matter
7. build_graph(domain=...)
8. general_research
```

## Reusing This Repo

To adapt this project for your own agent:

1. Update the base prompt in `harness_agent/prompts/SOUL.md`.
2. Replace or add skills in `harness_agent/skills/`.
3. Add domain-specific tools in `harness_agent/tools/`.
4. Wire new middleware into `harness_agent/middleware/__init__.py`.
5. Keep secrets in `.env`.

## Memory And Generated Files

On first run, the app creates local memory files under `memory/`. Agent outputs
or research notes may be saved under `reports/`.

These folders can contain local preferences, research history, or personal
output, so they are not included as reusable source files:

```text
memory/
reports/
```

## Project Layout

```text
agent_harness_lab/
  harness_agent/
    agent.py                 # LangGraph graph assembly
    main.py                  # CLI entry point
    llm/
      providers.py           # Azure OpenAI / Ollama factory
    middleware/
      base.py                # AgentMiddleware and MiddlewareStack
      skills.py              # dynamic skill loading and prompt injection
      todo.py                # write_todo_list tool and todo prompt rules
      patch_tool_calls.py    # repair dangling tool calls
      argument_truncation.py # trim old large tool-call arguments
      memory.py              # load/inject memory files
      compact.py             # summarize long conversations
      hitl.py                # approval helper for risky tool calls
    prompts/
      SOUL.md                # base prompt
    skills/
      general_research/
      job_search/
      stock_research/
      weather_reports/
    tools/
      datetime.py
      filesystem.py
      web_fetch.py
      web_search.py
  .env.example               # provider configuration template
  pyproject.toml             # package metadata and dependencies
  uv.lock                    # reproducible dependency lockfile
```

## Configuration

Provider preference is stored in:

```text
~/.agent-harness-lab/config.toml
```

The file is created automatically the first time the CLI runs. If
`AZURE_OPENAI_API_KEY` is present, the default provider is Azure OpenAI.
Otherwise, the default provider is Ollama.

Example config:

```toml
[llm]
provider = "ollama"
model = ""
```

Set `model` when you want to override the model or deployment from `.env`.
