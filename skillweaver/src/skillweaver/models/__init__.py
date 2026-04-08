"""SkillWeaver LLM backend abstraction.

SkillWeaver supports 4 decomposition backends out of the box:

- **rule**:   Rule-based splitting (no LLM, zero dependencies, good for testing)
- **ollama**: Ollama local server (default: qwen2.5:7b-instruct)
- **openai**: OpenAI-compatible API (default: gpt-4o-mini, also works with vLLM/together.ai)
- **local**:  HuggingFace transformers (default: Qwen/Qwen2.5-7B-Instruct, needs GPU)

Usage::

    from skillweaver.models import create_decomposer

    # Rule-based (no LLM needed)
    decomposer = create_decomposer("rule")

    # Ollama
    decomposer = create_decomposer("ollama", model="qwen2.5:7b-instruct")

    # OpenAI
    decomposer = create_decomposer("openai", model="gpt-4o-mini", api_key="sk-...")

    # Local transformers
    decomposer = create_decomposer("local", model_path="Qwen/Qwen2.5-7B-Instruct")

    subtasks = decomposer.decompose("scrape a website and analyze the data")
"""

from skillweaver.core.decomposer import (
    BaseDecomposer,
    LocalDecomposer,
    OllamaDecomposer,
    OpenAIDecomposer,
    RuleBasedDecomposer,
    create_decomposer,
)

__all__ = [
    "BaseDecomposer",
    "LocalDecomposer",
    "OllamaDecomposer",
    "OpenAIDecomposer",
    "RuleBasedDecomposer",
    "create_decomposer",
]
