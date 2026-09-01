# content of test_openholidays.py
from datetime import date
import pytest
import requests

import school_bell.openholidays as openholidays_module
from school_bell.openholidays import OpenHolidays

countryIsoCode = 'BE'
languageIsoCode = 'NL'
subdivisionCode = None
groupCode = 'BE-NL'

startDate = date(2024, 1, 1)
endDate = date(2024, 1, 10)

PUBLIC_HOLIDAY = {
    'startDate': '2024-01-01',
    'endDate': '2024-01-01',
    'type': 'Public',
    'nationwide': True,
}
SCHOOL_HOLIDAY = {
    'startDate': '2024-01-01',
    'endDate': '2024-01-07',
    'type': 'School',
    'nationwide': False,
}


class FakeResponse:
    def __init__(self, data=None, status_error=None):
        self.data = data
        self.status_error = status_error
        self.json_called = False

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        self.json_called = True
        return self.data


@pytest.fixture
def mocked_requests(monkeypatch):
    """Return deterministic API data and record every OpenHolidays request."""
    calls = []

    def get(url, params=None, **kwargs):
        calls.append((url, params, kwargs))
        path = url.rsplit('/', 1)[-1]
        requested_date = (params or {}).get(
            'date', (params or {}).get('validFrom')
        )
        if requested_date != '2024-01-01':
            return FakeResponse([])
        if path in ('PublicHolidays', 'PublicHolidaysByDate'):
            return FakeResponse([PUBLIC_HOLIDAY.copy()])
        if path in ('SchoolHolidays', 'SchoolHolidaysByDate'):
            return FakeResponse([SCHOOL_HOLIDAY.copy()])
        return FakeResponse([])

    monkeypatch.setattr(openholidays_module.requests, 'get', get)
    return calls


@pytest.fixture
def oh(mocked_requests):
    return OpenHolidays(
        countryIsoCode, languageIsoCode, subdivisionCode, groupCode
    )


def test_initialization_does_not_make_request(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail('OpenHolidays initialization made an HTTP request')

    monkeypatch.setattr(openholidays_module.requests, 'get', unexpected_request)
    OpenHolidays(countryIsoCode, languageIsoCode, groupCode=groupCode)


def test_request_uses_default_timeout(monkeypatch):
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse([])

    monkeypatch.setattr(openholidays_module.requests, 'get', get)
    OpenHolidays(countryIsoCode).countries()

    assert calls[0][1]['timeout'] == OpenHolidays.DEFAULT_TIMEOUT


def test_request_timeout_can_be_overridden(monkeypatch):
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse([])

    monkeypatch.setattr(openholidays_module.requests, 'get', get)
    OpenHolidays(countryIsoCode).countries(timeout=2)

    assert calls[0][1]['timeout'] == 2


def test_none_timeout_uses_default(monkeypatch):
    calls = []

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse([])

    monkeypatch.setattr(openholidays_module.requests, 'get', get)
    OpenHolidays(countryIsoCode).countries(timeout=None)

    assert calls[0][1]['timeout'] == OpenHolidays.DEFAULT_TIMEOUT


def test_http_status_is_checked_before_json_is_parsed(monkeypatch):
    response = FakeResponse(
        [], requests.exceptions.HTTPError('request failed')
    )
    monkeypatch.setattr(
        openholidays_module.requests, 'get', lambda *args, **kwargs: response
    )

    with pytest.raises(requests.exceptions.HTTPError):
        OpenHolidays(countryIsoCode).countries()

    assert response.json_called is False


def test_countryIsoCode(oh):
    assert oh.countryIsoCode == countryIsoCode


def test_languageIsoCode(oh):
    assert oh.languageIsoCode == languageIsoCode


def test_subdivisionCode(oh):
    assert oh.subdivisionCode == subdivisionCode


def test_groupCode(oh):
    assert oh.groupCode == groupCode


def test_url(oh):
    url = "https://openholidaysapi.org/swagger/v1/swagger.json"
    assert oh.url("swagger/v1/swagger.json") == url


def test_title(oh):
    assert isinstance(oh.title, str)


def test_description(oh):
    assert isinstance(oh.description, str)


def test_version(oh):
    assert isinstance(oh.version, str)


def test_isHoliday_true(oh):
    assert oh.isHoliday(startDate) is True


def test_isHoliday_false(oh):
    assert oh.isHoliday(endDate) is False


def test_publicHolidays(oh):
    r = oh.publicHolidays(startDate, endDate)
    assert r[0]['startDate'] == startDate
    assert r[0]['endDate'] == startDate
    assert r[0]['type'] == "Public"
    assert r[0]['nationwide'] is True


def test_publicHolidaysByDate(oh):
    r = oh.publicHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "Public"


def test_schoolHolidays(oh):
    r = oh.schoolHolidays(startDate, endDate)
    assert r[0]['type'] == "School"


def test_schoolHolidaysByDate(oh):
    r = oh.schoolHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "School"
