# SkillWeaver

**Compositional skill routing for LLM agents.** Describe a complex task in natural language — SkillWeaver decomposes it, finds the right skills, and composes an executable plan.

From the research paper: *Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose* (EMNLP 2026).

## Why SkillWeaver?

LLM agents have access to thousands of skills (MCP servers, SKILL.md files, OpenAI functions), but:
- **Context overflow**: 2,000+ tools × 400 tokens each = 800K tokens just for tool descriptions
- **No composition**: existing routers pick *one* tool per query, but real tasks need *multiple* tools working together
- **Format fragmentation**: SKILL.md, MCP, OpenAI Functions, LangChain — all different formats

SkillWeaver solves all three with a **decompose → retrieve → compose** pipeline and **Skill-Aware Decomposition (SAD)**, a retrieval-augmented feedback loop that improves routing accuracy by 60%.

## Quick Start

```bash
pip install skillweaver

# Index your skills (SKILL.md files)
skillweaver index ./my-skills/

# Search for a skill
skillweaver search "convert PDF to markdown"

# Compose a multi-skill workflow (with SAD for best results)
skillweaver plan "scrape website, analyze the data, generate charts, send to Slack" --sad
```

## How It Works

```
User query: "Scrape website, analyze data, generate charts, send to Slack"
                    │
        ┌───────────▼───────────┐
        │  Stage 1: Decompose   │  LLM breaks query into atomic sub-tasks
        │  (+ SAD feedback)     │  SAD: retrieval hints improve decomposition
        └───────────┬───────────┘
                    │  [t1: scrape, t2: analyze, t3: chart, t4: notify]
        ┌───────────▼───────────┐
        │  Stage 2: Retrieve    │  Bi-encoder + FAISS finds candidate skills
        └───────────┬───────────┘
                    │  top-k candidates per sub-task
        ┌───────────▼───────────┐
        │  Stage 3: Compose     │  DAG planner with compatibility scoring
        └───────────┬───────────┘
                    │
        web-scraper → data-analyzer → chart-gen → slack-notifier
```

**SAD (Skill-Aware Decomposition)** is the key innovation: it feeds retrieved skill names back into the decomposer, creating a vocabulary bridge between user language and skill metadata. A 7B model with SAD outperforms a 72B model without it.

## Features

- **Compositional routing** — automatically decomposes complex tasks into multi-skill workflows
- **SAD feedback loop** — retrieval-augmented decomposition improves accuracy by 60%
- **Multi-format support** — SKILL.md, MCP servers, OpenAI functions, LangChain tools
- **DAG planning** — detects parallelizable sub-tasks for concurrent execution
- **Context-aware filtering** — reduces token consumption by 99%+ via smart tool injection
- **Multiple LLM backends** — Ollama (local/free), OpenAI API, local transformers, rule-based
- **MCP proxy** — drop-in gateway that filters tools for any MCP-compatible agent

## Usage

### CLI

```bash
# Initialize (downloads lightweight embedding model, ~80MB)
skillweaver init

# Index skills from a directory
skillweaver index ./my-skills/
skillweaver index ./my-skills/ --format mcp  # MCP config files

# Semantic search
skillweaver search "parse PDF documents"
skillweaver search "deploy to kubernetes" --category deployment

# Compose a workflow
skillweaver plan "fetch API data, clean it, generate a report" --sad
skillweaver plan "..." --sad --dag  # with parallel detection
skillweaver plan "..." --backend openai --model gpt-4o-mini --sad

# MCP proxy (filters tools for any MCP-compatible agent)
skillweaver proxy --upstream ~/.config/mcp/servers.json

# HTTP API server
skillweaver serve
```

### Python SDK

```python
from skillweaver.sdk.client import SkillWeaverClient

sw = SkillWeaverClient()
sw.load_skills_from_directory("./skills")

# Search
results = sw.search("web scraping")

# Plan with SAD
plan = sw.plan(
    "fetch data from API, parse it, store in database",
    backend="ollama",
    use_dag=True,
)
print(plan.to_json())

# Filter tools for an agent (MCP proxy equivalent)
tools = sw.filter_tools("data analysis task", max_tools=10, token_budget=4000)
```

### MCP Proxy

Add SkillWeaver as a proxy in front of your MCP servers. It intercepts `tools/list` and returns only the relevant tools for each query:

```json
{
  "mcpServers": {
    "skillweaver": {
      "command": "skillweaver",
      "args": ["proxy", "--upstream", "path/to/mcp-config.json"]
    }
  }
}
```

## Encoder Note

By default, SkillWeaver uses `all-MiniLM-L6-v2` (80MB) for fast setup. The paper experiments use `BGE-large-en-v1.5` (1.2GB) for best accuracy. To switch:

```bash
# Use paper-grade encoder
SKILLWEAVER_ENCODER=BAAI/bge-large-en-v1.5 skillweaver plan "..." --sad

# Or set in config
echo "encoder: BAAI/bge-large-en-v1.5" >> ~/.skillweaver/config.yaml
```

## Configuration

SkillWeaver supports layered configuration (later overrides earlier):

1. Built-in defaults
2. User config: `~/.skillweaver/config.yaml`
3. Project config: `.skillweaver.yaml`
4. Environment: `SKILLWEAVER_*` variables
5. CLI flags

Key settings:
```yaml
encoder: sentence-transformers/all-MiniLM-L6-v2  # or BAAI/bge-large-en-v1.5
decomposer_backend: rule  # rule | ollama | openai | local
top_k: 10
alpha: 0.7  # retrieval vs compatibility weight
```

## Research

This tool implements the methods from:

> **Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose**
> Anonymous. EMNLP 2026 (under review).

Key findings:
- Task decomposition quality is the primary bottleneck in compositional routing
- Iterative SAD improves category recall from 33.9% to 54.2% (+60%) in a single iteration across 6 models (7B to API-level)
- SAD converges to a near-fixed-point (hint Jaccard > 0.89) within 2-3 iterations
- A 7B model with SAD outperforms a 72B model without it
- SAD generalizes to unseen skills (retains 88% of gain under category transfer)
- Metadata-only retrieval matches body-aware retrieval

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache-2.0
