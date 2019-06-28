import pytest

from larpix.larpix import Chip

@pytest.fixture
def chip():
    return Chip('1-2-3')
