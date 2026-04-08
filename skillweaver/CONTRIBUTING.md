# Contributing to SkillWeaver

Thanks for your interest in contributing.

## Development Setup

```bash
git clone https://github.com/skillweaver-ai/skillweaver.git
cd skillweaver
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Pull Request Process

1. Fork the repo and create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass and ruff is clean
4. Submit a PR with a clear description

## Reporting Issues

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- SkillWeaver version (`skillweaver --version`)
