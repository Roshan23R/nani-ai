"""The extraction prompt must never drift from the tuned prototype.

It is the product of four tuning rounds against real handwritten
prescriptions. If this test fails, someone edited one copy and not the other —
reconcile them deliberately, do not just update the expected value.
"""

import importlib.util
from pathlib import Path

import pytest

from agents import prompts

PROTOTYPE = Path(__file__).resolve().parents[1] / "scripts" / "test_extraction.py"


@pytest.fixture(scope="module")
def prototype():
    spec = importlib.util.spec_from_file_location("test_extraction_prototype", PROTOTYPE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_system_prompt_is_verbatim(prototype):
    assert prompts.SYSTEM_PROMPT == prototype.SYSTEM_PROMPT


def test_user_prompt_is_verbatim(prototype):
    assert prompts.USER_PROMPT == prototype.USER_PROMPT


def test_investigation_list_is_not_framed_as_a_menu():
    """The single change that took Sonnet from 3/4-with-a-fabrication to 4/4."""
    assert "It is NOT a menu." in prompts.SYSTEM_PROMPT
    assert "ONLY to help you recognise shorthand you actually see" in prompts.SYSTEM_PROMPT
