# content of conftest.py
import pytest
import requests


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


@pytest.fixture(autouse=True)
def block_unmocked_http_requests(monkeypatch):
    """Fail fast if a test attempts an unmocked requests HTTP call."""
    def blocked_request(*args, **kwargs):
        raise requests.exceptions.ConnectionError(
            'Tests must mock external HTTP requests'
        )

    monkeypatch.setattr(requests.sessions.Session, 'request', blocked_request)
