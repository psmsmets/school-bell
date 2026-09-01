# content of test_openholidays.py
from datetime import date
import pytest
import requests

import school_bell.openholidays as openholidays_module
from school_bell.openholidays import OpenHolidays
from school_bell.utils import to_date

countryIsoCode = 'BE'
languageIsoCode = 'NL'
subdivisionCode = None
groupCode = 'BE-NL'

startDate = to_date(date.today().strftime("%Y-01-01"))
endDate = to_date(date.today().strftime("%Y-01-10"))

oh = OpenHolidays(countryIsoCode, languageIsoCode, subdivisionCode, groupCode)


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


def test_countryIsoCode():
    assert oh.countryIsoCode == countryIsoCode


def test_languageIsoCode():
    assert oh.languageIsoCode == languageIsoCode


def test_subdivisionCode():
    assert oh.subdivisionCode == subdivisionCode


def test_groupCode():
    assert oh.groupCode == groupCode


def test_url():
    url = "https://openholidaysapi.org/swagger/v1/swagger.json"
    assert oh.url("swagger/v1/swagger.json") == url


def test_title():
    assert isinstance(oh.title, str)


def test_description():
    assert isinstance(oh.description, str)


def test_version():
    assert isinstance(oh.version, str)


def test_isHoliday_true():
    assert oh.isHoliday(startDate) is True


def test_isHoliday_false():
    assert oh.isHoliday(endDate) is False


def test_publicHolidays():
    r = oh.publicHolidays(startDate, endDate)
    assert r[0]['startDate'] == startDate
    assert r[0]['endDate'] == startDate
    assert r[0]['type'] == "Public"
    assert r[0]['nationwide'] is True


def test_publicHolidaysByDate():
    r = oh.publicHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "Public"


def test_schoolHolidays():
    r = oh.schoolHolidays(startDate, endDate)
    assert r[0]['type'] == "School"


def test_schoolHolidaysByDate():
    r = oh.schoolHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "School"
