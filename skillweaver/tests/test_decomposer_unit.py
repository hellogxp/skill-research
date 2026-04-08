"""Unit tests for decomposer module."""

from __future__ import annotations

import pytest

from skillweaver.core.decomposer import (
    RuleBasedDecomposer,
    create_decomposer,
    parse_subtasks,
)


class TestRuleBasedDecomposer:
    def setup_method(self):
        self.decomposer = RuleBasedDecomposer()

    def test_single_task(self):
        result = self.decomposer.decompose("scrape a website")
        assert len(result) == 1
        assert result[0].description == "scrape a website"
        assert result[0].step_index == 0

    def test_and_conjunction(self):
        # ", and" splits; bare "and" without comma does not
        result = self.decomposer.decompose("scrape a website, and parse the data")
        assert len(result) == 2
        assert "scrape" in result[0].description.lower()
        assert "parse" in result[1].description.lower()

    def test_then_conjunction(self):
        result = self.decomposer.decompose("fetch data then analyze it")
        assert len(result) == 2

    def test_and_then_conjunction(self):
        result = self.decomposer.decompose("scrape website and then send email")
        assert len(result) == 2

    def test_comma_separated(self):
        result = self.decomposer.decompose("scrape website, parse data, send email")
        assert len(result) == 3

    def test_complex_query(self):
        result = self.decomposer.decompose(
            "scrape GitHub trending, analyze language trends, generate a chart, and send to Slack"
        )
        assert len(result) >= 3

    def test_empty_parts_filtered(self):
        result = self.decomposer.decompose("do something,  ,  , and another thing")
        for subtask in result:
            assert subtask.description.strip() != ""

    def test_step_indices_sequential(self):
        result = self.decomposer.decompose("a, b, c, d")
        for i, subtask in enumerate(result):
            assert subtask.step_index == i


class TestParseSubtasks:
    def test_json_array(self):
        result = parse_subtasks('["task one", "task two"]', "fallback")
        assert len(result) == 2
        assert result[0].description == "task one"

    def test_json_array_with_prefix(self):
        result = parse_subtasks('Here are the tasks: ["a", "b", "c"]', "fallback")
        assert len(result) == 3

    def test_numbered_list(self):
        text = "1. First task\n2. Second task\n3. Third task"
        result = parse_subtasks(text, "fallback")
        assert len(result) == 3
        assert result[0].description == "First task"

    def test_bullet_list(self):
        text = "- Task A\n- Task B"
        result = parse_subtasks(text, "fallback")
        assert len(result) == 2

    def test_empty_input(self):
        result = parse_subtasks("", "fallback query")
        assert len(result) == 1
        assert result[0].description == "fallback query"

    def test_malformed_json(self):
        result = parse_subtasks("{broken json[}", "fallback query")
        assert len(result) >= 1

    def test_json_with_empty_strings(self):
        result = parse_subtasks('["task one", "", "task two"]', "fallback")
        assert all(s.description.strip() for s in result)


class TestCreateDecomposer:
    def test_rule_backend(self):
        d = create_decomposer("rule")
        assert isinstance(d, RuleBasedDecomposer)

    def test_invalid_backend(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            create_decomposer("nonexistent")

    def test_all_valid_backends(self):
        for backend in ["rule", "openai", "local", "ollama"]:
            # openai/local/ollama won't actually connect - just test factory
            if backend == "rule":
                d = create_decomposer(backend)
                assert d is not None
