from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_REPO = FIXTURES / "sample_repo"


@pytest.fixture
def sample_repo():
    return SAMPLE_REPO


@pytest.fixture
def read_fixture():

    def read(relative_path):
        return (SAMPLE_REPO / relative_path).read_text(encoding="utf-8")

    return read
