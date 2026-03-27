# SkillWeaver

**AI Agent skill discovery and compositional workflow orchestration.**

Describe what you want to do in natural language. SkillWeaver finds the right skills and composes them into an executable plan.

## Quick Start

```bash
pip install skillweaver

# Initialize
skillweaver init

# Index your skills
skillweaver index ./my-skills/

# Search for a skill
skillweaver search "convert PDF to markdown"

# Auto-compose a workflow
skillweaver plan "scrape website, analyze data, generate charts, send to slack"
```

## Features

- **Semantic skill search** - Find skills using natural language queries (BGE + FAISS)
- **Auto task decomposition** - Break complex tasks into atomic sub-tasks using LLMs
- **Compositional routing** - Match each sub-task to the best skill from your library
- **Multi-format support** - SKILL.md, MCP servers, OpenAI functions
- **Multiple LLM backends** - Ollama (local/free), OpenAI API, local transformers

## How It Works

SkillWeaver implements a three-stage **Decompose-Retrieve-Compose** pipeline:

1. **Decompose**: An LLM breaks your complex query into atomic sub-tasks
2. **Retrieve**: A bi-encoder finds candidate skills for each sub-task
3. **Compose**: A compatibility-aware planner selects the best skill chain

Based on the research paper: *Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose* (2026).

## License

Apache-2.0
