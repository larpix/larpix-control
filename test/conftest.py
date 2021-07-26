import pytest

from larpix.larpix import Chip

@pytest.fixture
def chip():
    return Chip('1-2-3')

@pytest.fixture
def chip2b():
    return Chip('1-2-3', version='2b')
