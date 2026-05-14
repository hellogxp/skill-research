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

SYSTEM_PROMPT = (
    "You are a task decomposition expert. Given a user query that requires multiple "
    "tools/skills to complete, break it down into a sequence of atomic sub-tasks.\n\n"
    "Rules:\n"
    "1. Each sub-task should require exactly ONE skill/tool to complete.\n"
    "2. List sub-tasks in execution order.\n"
    "3. Be specific about what each sub-task does.\n"
    "4. Output ONLY a JSON array of strings, nothing else."
)

USER_TEMPLATE = """Decompose this query into atomic sub-tasks. Output a JSON array of strings ONLY.

Query: {query}

JSON array:"""

SAD_USER_TEMPLATE = (
    "Decompose the following query into atomic sub-tasks. "
    "Output a JSON array of strings ONLY.\n"
    "Available skills that may be relevant: {hint_list}\n\n"
    "Query: {query}\n\n"
    "JSON array:"
)


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

    def decompose_with_hints(self, query: str, hints: list[str]) -> list[SubTask]:
        """SAD Pass 2: re-decompose with skill hints.

        Subclasses backed by an LLM override this to inject hints into
        the prompt.  The default implementation falls back to vanilla
        decompose (useful for rule-based backends that cannot use hints).
        """
        return self.decompose(query)

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

    def decompose_with_hints(self, query: str, hints: list[str]) -> list[SubTask]:
        self._init_client()
        hint_list = ", ".join(hints)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": SAD_USER_TEMPLATE.format(
                    query=query, hint_list=hint_list,
                )},
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
        load_in_4bit: bool = False,
    ):
        self.model_path = model_path
        self.device = device
        self.temperature = temperature
        self.load_in_4bit = load_in_4bit
        self._model = None
        self._tokenizer = None

    @staticmethod
    def _estimate_model_size_gb(model_path: str) -> float:
        """Estimate model size in GB from config.json."""
        import json
        from pathlib import Path

        config_path = Path(model_path) / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                cfg = json.load(f)
            # Try num_params first (some models provide this)
            num_params = cfg.get("num_params")
            if num_params is None:
                # Estimate from architecture params
                vocab = cfg.get("vocab_size", 32000)
                hidden = cfg.get("hidden_size", 4096)
                layers = cfg.get("num_hidden_layers", 32)
                intermediate = cfg.get("intermediate_size", hidden * 4)
                # Attention params per layer: 4 * hidden^2 (Q,K,V,O)
                # FFN params per layer: 2 * hidden * intermediate
                num_params = vocab * hidden + layers * (
                    4 * hidden * hidden + 2 * hidden * intermediate + 2 * hidden
                )
            return num_params * 2 / (1024 ** 3)  # fp16 = 2 bytes
        return 0.0

    def _build_load_kwargs(self) -> dict:
        """Build kwargs for AutoModelForCausalLM.from_pretrained.

        Ensures model runs on GPU with NO CPU offload.
        Strategy:
          - Model fits on 1 GPU → device_map={"": 0} (direct, no accelerate)
          - Model needs multi-GPU → device_map="auto" + max_memory (no CPU)
          - Model too large for all GPUs → 4-bit quantization
        """
        import torch

        kwargs = {"trust_remote_code": True}

        # If device is explicitly specified (not "auto"), use it directly
        if self.device != "auto":
            if self.load_in_4bit:
                from transformers import BitsAndBytesConfig
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                kwargs["device_map"] = self.device
            else:
                kwargs["torch_dtype"] = torch.float16
                kwargs["device_map"] = self.device
            return kwargs

        # device="auto" with GPU allocation guard
        num_gpus = torch.cuda.device_count()
        model_size_gb = self._estimate_model_size_gb(self.model_path)
        single_gpu_gb = (
            torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if num_gpus > 0 else 0
        )
        total_gpu_gb = sum(
            torch.cuda.get_device_properties(i).total_memory
            for i in range(num_gpus)
        ) / (1024 ** 3)

        logger.info(
            f"Model ~{model_size_gb:.1f}GB, "
            f"{num_gpus} GPUs = {total_gpu_gb:.1f}GB total"
        )

        # Strategy 1: Single GPU — direct placement (most reliable)
        if num_gpus >= 1 and model_size_gb <= single_gpu_gb:
            kwargs["torch_dtype"] = torch.float16
            kwargs["device_map"] = {"": 0}
            logger.info("Strategy: single-GPU direct placement (cuda:0)")

        # Strategy 2: Multi-GPU with max_memory (no CPU offload)
        elif model_size_gb <= total_gpu_gb * 0.95:
            kwargs["torch_dtype"] = torch.float16
            kwargs["device_map"] = "auto"
            max_memory = {}
            for i in range(num_gpus):
                mem_gb = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)
                max_memory[i] = f"{int(mem_gb - 1)}GiB"  # Reserve 1GB for activations
            max_memory["cpu"] = "0GiB"  # NO CPU offload
            kwargs["max_memory"] = max_memory
            logger.info(f"Strategy: multi-GPU max_memory = {max_memory}")

        # Strategy 3: Model too large → 4-bit quantization with manual device_map
        elif self.load_in_4bit or model_size_gb > total_gpu_gb * 0.95:
            logger.warning(
                f"Model ({model_size_gb:.1f}GB) too large for GPU memory "
                f"({total_gpu_gb:.1f}GB). Using 4-bit quantization."
            )
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            # Manual device_map: distribute layers evenly across GPUs
            # (device_map="auto" fails with quantization due to size estimation bug)
            kwargs["device_map"] = self._build_balanced_device_map()
            logger.info("Strategy: 4-bit quantization with manual device_map")

        return kwargs

    def _build_balanced_device_map(self) -> dict:
        """Build a manual device_map that distributes model layers evenly across GPUs.

        This avoids the `device_map="auto"` bug where accelerate uses fp16 size
        estimation even for quantized models, causing incorrect offload decisions.
        """
        import json
        import torch
        from pathlib import Path

        config_path = Path(self.model_path) / "config.json"
        num_gpus = torch.cuda.device_count()

        if config_path.exists():
            with open(config_path) as f:
                cfg = json.load(f)
            num_layers = cfg.get("num_hidden_layers", 32)
        else:
            num_layers = 32

        device_map = {}
        device_map["model.embed_tokens"] = 0
        device_map["model.norm"] = num_gpus - 1
        device_map["lm_head"] = num_gpus - 1

        layers_per_gpu = num_layers // num_gpus
        extra = num_layers % num_gpus
        layer_idx = 0
        for gpu in range(num_gpus):
            count = layers_per_gpu + (1 if gpu < extra else 0)
            for _ in range(count):
                device_map[f"model.layers.{layer_idx}"] = gpu
                layer_idx += 1

        logger.info(
            f"Manual device_map: {num_layers} layers across {num_gpus} GPUs"
        )
        return device_map

    def _init_model(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"Loading local model: {self.model_path}")
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, trust_remote_code=True
        )

        load_kwargs = self._build_load_kwargs()
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path, **load_kwargs
        )
        self._model.eval()

        # Verify no CPU offload occurred
        device_map = getattr(self._model, "hf_device_map", None)
        if device_map is not None:
            cpu_layers = [k for k, v in device_map.items() if str(v) == "cpu"]
            if cpu_layers:
                logger.error(
                    f"CRITICAL: {len(cpu_layers)} layers offloaded to CPU! "
                    f"Results will be unreliable. Consider using load_in_4bit=True."
                )
            else:
                devices_used = set(str(v) for v in device_map.values())
                logger.info(f"Model loaded on GPU(s): {devices_used}")
        else:
            # device_map={"": N} direct placement — always on GPU
            logger.info("Model loaded on GPU (direct placement)")

    def _generate(self, messages: list[dict]) -> str:
        import torch

        self._init_model()

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
        return self._tokenizer.decode(
            output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
        ).strip()

    def decompose(self, query: str) -> list[SubTask]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(query=query)},
        ]
        text = self._generate(messages)
        return parse_subtasks(text, query)

    def decompose_with_hints(self, query: str, hints: list[str]) -> list[SubTask]:
        hint_list = ", ".join(hints)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SAD_USER_TEMPLATE.format(
                query=query, hint_list=hint_list,
            )},
        ]
        text = self._generate(messages)
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

    def _call_ollama(self, messages: list[dict]) -> str:
        import httpx

        response = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "options": {"temperature": self.temperature},
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def decompose(self, query: str) -> list[SubTask]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(query=query)},
        ]
        text = self._call_ollama(messages)
        return parse_subtasks(text, query)

    def decompose_with_hints(self, query: str, hints: list[str]) -> list[SubTask]:
        hint_list = ", ".join(hints)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SAD_USER_TEMPLATE.format(
                query=query, hint_list=hint_list,
            )},
        ]
        text = self._call_ollama(messages)
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
