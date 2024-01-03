# content of conftest.py
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--device",
        action="store",
        default=None,
        help='Set the alsa device. Defaults to `None`.'
    )


@pytest.fixture
def device(request):
    return request.config.getoption('--device')
