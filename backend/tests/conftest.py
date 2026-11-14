import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_work() -> dict:
    """A real OpenAlex work (W4413844203) trimmed of bulky fields.

    8 authors across US/CA/DK institutions; the first author has no OpenAlex author id.
    """
    return json.loads((FIXTURES / "work.json").read_text())
