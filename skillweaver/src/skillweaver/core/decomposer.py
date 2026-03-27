"""Task decomposer: breaks complex queries into atomic sub-tasks.

Supports multiple LLM backends (local transformers, OpenAI API, Ollama).
Adapted from the Compositional Skill Routing paper's TaskDecomposer.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

from skillweaver.core.models import SubTask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task decomposition expert. Given a user query that requires multiple tools/skills to complete, break it down into a sequence of atomic sub-tasks.

Rules:
1. Each sub-task should require exactly ONE skill/tool to complete.
2. List sub-tasks in execution order.
3. Be specific about what each sub-task does.
4. Output ONLY a JSON array of strings, nothing else."""

USER_TEMPLATE = """Decompose this query into atomic sub-tasks. Output a JSON array of strings ONLY.

Query: {query}

JSON array:"""


def parse_subtasks(text: str, fallback_query: str) -> list[SubTask]:
    """Parse LLM output into SubTask objects."""
    text = text.strip()

    # Try JSON array
    try:
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            items = json.loads(match.group())
            if isinstance(items, list) and len(items) > 0:
                return [
                    SubTask(step_index=i, description=str(s).strip())
                    for i, s in enumerate(items)
                    if str(s).strip()
                ]
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: numbered list
    lines = []
    for line in text.split("\n"):
        cleaned = re.sub(r"^[\d]+[.)]\s*", "", line.strip())
        cleaned = re.sub(r"^[-*]\s*", "", cleaned)
        cleaned = cleaned.strip().strip("\"'")
        if cleaned:
            lines.append(cleaned)

    if lines:
        return [SubTask(step_index=i, description=s) for i, s in enumerate(lines)]

    # Last resort
    return [SubTask(step_index=0, description=fallback_query)]


class BaseDecomposer(ABC):
    """Abstract base class for task decomposers."""

    @abstractmethod
    def decompose(self, query: str) -> list[SubTask]:
        """Decompose a query into sub-tasks."""
        ...

    def decompose_batch(self, queries: list[str]) -> list[list[SubTask]]:
        """Decompose multiple queries. Default: sequential."""
        results = []
        for i, q in enumerate(queries):
            results.append(self.decompose(q))
            if (i + 1) % 20 == 0:
                logger.info(f"  Decomposed {i + 1}/{len(queries)}")
        return results


class OpenAIDecomposer(BaseDecomposer):
    """Decomposer using OpenAI-compatible API (OpenAI, together.ai, vLLM, etc.)."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.1,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.temperature = temperature
        self._client = None

    def _init_client(self):
        if self._client is not None:
            return
        from openai import OpenAI

        kwargs = {}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        self._client = OpenAI(**kwargs)

    def decompose(self, query: str) -> list[SubTask]:
        self._init_client()
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(query=query)},
            ],
            temperature=self.temperature,
            max_tokens=512,
        )
        text = response.choices[0].message.content or ""
        return parse_subtasks(text, query)


class LocalDecomposer(BaseDecomposer):
    """Decomposer using a local transformers model."""

    def __init__(
        self,
        model_path: str = "Qwen/Qwen2.5-7B-Instruct",
        device: str = "auto",
        temperature: float = 0.1,
    ):
        self.model_path = model_path
        self.device = device
        self.temperature = temperature
        self._model = None
        self._tokenizer = None

    def _init_model(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"Loading local model: {self.model_path}")
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, trust_remote_code=True
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16,
            device_map=self.device,
            trust_remote_code=True,
        )
        self._model.eval()
        logger.info("Model loaded.")

    def decompose(self, query: str) -> list[SubTask]:
        import torch

        self._init_model()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(query=query)},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=self.temperature,
                do_sample=True,
            )
        text = self._tokenizer.decode(
            output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
        ).strip()

        return parse_subtasks(text, query)


class OllamaDecomposer(BaseDecomposer):
    """Decomposer using Ollama local server."""

    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        host: str = "http://localhost:11434",
        temperature: float = 0.1,
    ):
        self.model = model
        self.host = host
        self.temperature = temperature

    def decompose(self, query: str) -> list[SubTask]:
        import httpx

        response = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(query=query)},
                ],
                "options": {"temperature": self.temperature},
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        text = response.json()["message"]["content"]
        return parse_subtasks(text, query)


class RuleBasedDecomposer(BaseDecomposer):
    """Simple rule-based decomposer for testing/demo without an LLM.

    Splits queries on common conjunction patterns (\"and\", \"then\", commas).
    Falls back to the full query as a single step if no splits are found.
    """

    def decompose(self, query: str) -> list[SubTask]:
        import re

        # Split on "and then", "then", ", and", ", "
        parts = re.split(r"\s+and\s+then\s+|\s+then\s+|,\s*and\s+|,\s+", query, flags=re.IGNORECASE)
        parts = [p.strip().strip("\"'") for p in parts if p.strip()]

        if not parts:
            parts = [query]

        return [SubTask(step_index=i, description=s) for i, s in enumerate(parts)]


def create_decomposer(backend: str = "ollama", **kwargs) -> BaseDecomposer:
    """Factory function to create a decomposer by backend name."""
    backends = {
        "openai": OpenAIDecomposer,
        "local": LocalDecomposer,
        "ollama": OllamaDecomposer,
        "rule": RuleBasedDecomposer,
    }
    cls = backends.get(backend)
    if cls is None:
        raise ValueError(f"Unknown backend: {backend}. Choose from: {list(backends)}")
    return cls(**kwargs)
