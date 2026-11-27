<p align="center"><img src="https://cleanedweb.com/assets/logo.png" width="72" alt="CleanedWeb"></p>

# LlamaIndex Tool Spec: CleanedWeb

[![PyPI](https://img.shields.io/pypi/v/llama-index-tools-cleanedweb)](https://pypi.org/project/llama-index-tools-cleanedweb/) [![CI](https://github.com/cleanedweb/llama-index-tools-cleanedweb/actions/workflows/ci.yml/badge.svg)](https://github.com/cleanedweb/llama-index-tools-cleanedweb/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/cleanedweb/llama-index-tools-cleanedweb/blob/main/LICENSE)

<p align="center"><img src="https://raw.githubusercontent.com/cleanedweb/llama-index-tools-cleanedweb/main/docs/demo.gif" width="760" alt="Terminal: the LlamaIndex tool spec finds the Steam Most Played Games API and prints five live records"></p>
<p align="center"><sub>A live run: the five most played Steam games right now, as five records.</sub></p>

**Scrapers break whenever a site changes its pages.** CleanedWeb is a catalog of maintained REST APIs
for public websites (listings, products, jobs, articles, profiles): you call an API and get structured
records with known fields. When a site changes, CleanedWeb rebuilds its API.
This is the LlamaIndex tool spec for [CleanedWeb](https://cleanedweb.com/?utm_source=github&utm_medium=llama-index-tools-cleanedweb).

- `CleanedWebToolSpec` gives a LlamaIndex agent three tools: `find_api`, `get_api` and `run_api`.
- Finding and reading are free and need no key; only running is charged, per record.
- Guard rails for agents: small `max_items` by default, a hard cap, and records marked as data, never instructions.
- A slow run returns its idempotency key, so a retry reads the same run and is never charged twice.
- Every tool has an async twin that agents use automatically.

**Pricing:** 5,000 records free once, then prepaid credit from $1 per 1,000 records, no subscription.
Runs are charged per record delivered.
[Pricing](https://cleanedweb.com/pricing/?utm_source=github&utm_medium=llama-index-tools-cleanedweb)

## Install

```bash
pip install llama-index-tools-cleanedweb
```

`llama-index-tools-cleanedweb` depends on [`cleanedweb`](https://github.com/cleanedweb/cleanedweb-python).

Create an API key with the `run` scope in the [console](https://app.cleanedweb.com/) and export it as
`CLEANEDWEB_API_KEY`. Finding and reading APIs needs no key.

## Usage

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI  # or any LlamaIndex LLM
from llama_index.tools.cleanedweb import CleanedWebToolSpec

tools = CleanedWebToolSpec().to_tool_list()  # find_api, get_api, run_api
agent = FunctionAgent(tools=tools, llm=OpenAI(model="gpt-4.1"))

print(await agent.run("Get 5 trending Python repositories from GitHub topics."))
```

| Tool | Needs key | What it does |
| --- | --- | --- |
| `find_api(site, fields, query, limit)` | no | Find published APIs for a site or topic. Nothing runs. |
| `get_api(api_id)` | no | Inputs, output fields, limitations and three saved sample records. |
| `run_api(api_id, endpoint_id, input, max_items, idempotency_key)` | yes (`run`) | Run an endpoint and return its records. Charged per record. |

The tool descriptions tell the model to find before it runs, to start with a small `max_items`, and that
records are website data, never instructions. The spec also enforces it: `max_items` defaults to
`default_max_items=5` and is capped by `max_items_limit=100`. A run still going after `wait_seconds`
(default 60) returns `status: running` with its `idempotency_key`; calling `run_api` again with the same
arguments and key reads the same run and never starts or charges a second one. Client errors (no credit,
rate limit, failed run, lost connection) come back as short, actionable JSON text for the model; pass
`raise_on_error=True` to raise them instead. Every tool has an async twin (`afind_api`, `aget_api`,
`arun_api`) that the agent uses automatically.

`CleanedWebToolSpec(api_key=..., base_url=..., client=...)` overrides the defaults. To leave out the
paid tool: `CleanedWebToolSpec().to_tool_list(spec_functions=[("find_api", "afind_api"), ("get_api", "aget_api")])`.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ../cleanedweb-python -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest
```

Tests mock the HTTP layer; nothing in them calls the network or runs an API.

## More

- [Python guide](https://cleanedweb.com/docs/python/?utm_source=github&utm_medium=llama-index-tools-cleanedweb),
  [run a catalog API](https://cleanedweb.com/docs/run-catalog-api/?utm_source=github&utm_medium=llama-index-tools-cleanedweb)
- Prefer MCP? The hosted server is [cleanedweb/cleanedweb-mcp](https://github.com/cleanedweb/cleanedweb-mcp).

MIT licensed.
