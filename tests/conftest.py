"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def minimal_tex():
    return (FIXTURES_DIR / "minimal.tex").read_text()


@pytest.fixture
def full_paper_tex():
    return (FIXTURES_DIR / "full_paper.tex").read_text()


@pytest.fixture
def tmp_output(tmp_path):
    return tmp_path
