# Agent Harness Lab

Agent Harness Lab is a small LangGraph-based agent runtime for experimenting
with skills, middleware, memory, and tool use from a local CLI.

It is designed as a reusable starting point: clone it, configure an LLM
provider, run the CLI, then add your own skills, tools, and middleware.

## What You Get

- A LangGraph chat agent with a simple CLI.
- Skill routing based on commands, active domain, aliases, and trigger words.
- Built-in skills for general research, stock research, job search, and weather.
- Local memory files that are loaded into the agent prompt at runtime.
- Middleware for todo tracking, skill injection, memory injection, context
  compaction, tool-call cleanup, and risky tool approval.
- Tool support for filesystem operations, web search, web fetch, and datetime.
- Provider support for Azure OpenAI and Ollama.

## Requirements

- Python 3.14 or newer
- `uv`
- One LLM provider:
  - Azure OpenAI, or
  - Ollama running locally

## Quick Start

Clone the repo and install dependencies:

```bash
git clone <your-repo-url>
cd agent_harness_lab
uv sync
```

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit `.env` for either Azure OpenAI or Ollama.

Run the CLI:

```bash
uv run agent-harness-lab --help
```

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

Then run:

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

Then run:

```bash
uv run agent-harness-lab chat --provider ollama
```

## CLI Commands

Show all commands:

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

## Skills

Skills are prompt packages stored under:

```text
harness_agent/skills/<skill_id>/
  SKILL.md
  manifest.toml
```

`SKILL.md` contains the instructions that are injected into the agent prompt.
`manifest.toml` controls routing:

```toml
id = "stock_research"
name = "Stock Research"
aliases = ["stock", "stocks", "market", "finance"]
triggers = ["stock", "earnings", "valuation", "股票", "股價"]
```

Skill selection priority:

```text
1. /skill or /domain command in the latest user message
2. state["pinned_skills"]
3. state["active_skills"]
4. state["active_domain"]
5. trigger keyword routing from the latest user message
6. build_graph(domain=...)
7. general_research
```

Built-in skills:

- `general_research`
- `stock_research`
- `job_search`
- `weather_reports`

To add a new skill:

1. Create `harness_agent/skills/<your_skill>/`.
2. Add `SKILL.md`.
3. Add `manifest.toml`.
4. Run `uv run agent-harness-lab skills` to confirm it loads.

## Memory And Generated Files

On first run, the app creates local memory files under `memory/`. Agent outputs
or research notes may be saved under `reports/`.

These folders are intentionally ignored by git because they can contain local
preferences, research history, or personal output:

```text
memory/
reports/
```

Share reusable examples through documentation or fixtures instead of committing
your personal runtime files.

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

## Development

Run the package through `uv`:

```bash
uv run python -m harness_agent.main --help
```

Check that the project imports:

```bash
uv run python -m compileall harness_agent
```

Before publishing to GitHub, verify that only source, docs, examples, and
configuration templates are staged:

```bash
git status --short --ignored
```

Do not commit `.env`, `.venv/`, `memory/`, `reports/`, `__pycache__/`, or
`*.egg-info/`.
