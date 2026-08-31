import datetime
import logging

import pytest
import requests

import school_bell.disable_calendar as calendar_module
from school_bell.disable_calendar import DisableCalendar


TZ = datetime.timezone(datetime.timedelta(hours=2))


def ics(*events, extra=''):
    return (
        'BEGIN:VCALENDAR\r\n'
        'VERSION:2.0\r\n'
        'PRODID:-//school-bell tests//EN\r\n'
        f'{extra}'
        + ''.join(events) +
        'END:VCALENDAR\r\n'
    ).encode()


def event(*lines):
    return 'BEGIN:VEVENT\r\n' + '\r\n'.join(lines) + '\r\nEND:VEVENT\r\n'


class Response:
    def __init__(self, content, status=200):
        self.content = content
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f'HTTP {self.status}')


def calendar_with(monkeypatch, content):
    monkeypatch.setattr(
        calendar_module.requests,
        'get',
        lambda *_args, **_kwargs: Response(content),
    )
    calendar = DisableCalendar(
        'https://calendar.example/private-token/basic.ics',
        timezone='Europe/Brussels',
    )
    assert calendar.refresh() is True
    return calendar


@pytest.mark.parametrize(
    'moment, blocked',
    [
        (datetime.datetime(2026, 9, 13, 12, tzinfo=TZ), False),
        (datetime.datetime(2026, 9, 14, 0, tzinfo=TZ), True),
        (datetime.datetime(2026, 9, 14, 23, 59, tzinfo=TZ), True),
        (datetime.datetime(2026, 9, 15, 0, tzinfo=TZ), False),
    ],
)
def test_google_single_day_all_day_event(monkeypatch, moment, blocked):
    calendar = calendar_with(monkeypatch, ics(event(
        'UID:google-all-day@example.com',
        'DTSTART;VALUE=DATE:20260914',
        'DTEND;VALUE=DATE:20260915',
        'SUMMARY:School closed',
    )))

    match = calendar.blocking_event(moment)

    assert (match is not None) is blocked
    if match:
        assert match['summary'] == 'School closed'
        assert match['all_day'] is True


def test_outlook_timezone_timed_and_multi_day_events(monkeypatch):
    content = ics(
        event(
            'UID:outlook-meeting@example.com',
            'DTSTART;TZID=Europe/Brussels:20260914T090000',
            'DTEND;TZID=Europe/Brussels:20260914T100000',
            'SUMMARY:Staff meeting',
        ),
        event(
            'UID:outlook-closure@example.com',
            'DTSTART;VALUE=DATE:20260916',
            'DTEND;VALUE=DATE:20260919',
            'SUMMARY:Building closed',
        ),
        extra='X-WR-TIMEZONE:Europe/Brussels\r\n',
    )
    calendar = calendar_with(monkeypatch, content)

    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 8, 59, tzinfo=TZ)
    ) is None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 9, 30, tzinfo=TZ)
    )['summary'] == 'Staff meeting'
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 10, 0, tzinfo=TZ)
    ) is None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 18, 12, 0, tzinfo=TZ)
    )['summary'] == 'Building closed'
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 19, 0, 0, tzinfo=TZ)
    ) is None


def test_long_timed_period_crosses_midnight(monkeypatch):
    calendar = calendar_with(monkeypatch, ics(event(
        'UID:long-period@example.com',
        'DTSTART:20260914T220000Z',
        'DTEND:20260916T080000Z',
        'SUMMARY:Maintenance',
    )))

    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 15, 12, tzinfo=TZ)
    )['summary'] == 'Maintenance'


def test_recurring_event_exdate_and_cancelled_exception(monkeypatch):
    calendar = calendar_with(monkeypatch, ics(
        event(
            'UID:weekly@example.com',
            'DTSTART;VALUE=DATE:20260907',
            'DTEND;VALUE=DATE:20260908',
            'RRULE:FREQ=WEEKLY;COUNT=4',
            'EXDATE;VALUE=DATE:20260914',
            'SUMMARY:Weekly closure',
        ),
        event(
            'UID:weekly@example.com',
            'RECURRENCE-ID;VALUE=DATE:20260921',
            'DTSTART;VALUE=DATE:20260921',
            'DTEND;VALUE=DATE:20260922',
            'STATUS:CANCELLED',
            'SUMMARY:Cancelled closure',
        ),
    ))

    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 7, 12, tzinfo=TZ)
    ) is not None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 12, tzinfo=TZ)
    ) is None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 21, 12, tzinfo=TZ)
    ) is None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 28, 12, tzinfo=TZ)
    ) is not None


def test_recurrence_id_moves_one_occurrence(monkeypatch):
    calendar = calendar_with(monkeypatch, ics(
        event(
            'UID:moved@example.com',
            'DTSTART;TZID=Europe/Brussels:20260907T090000',
            'DTEND;TZID=Europe/Brussels:20260907T100000',
            'RRULE:FREQ=WEEKLY;COUNT=2',
            'SUMMARY:Recurring maintenance',
        ),
        event(
            'UID:moved@example.com',
            'RECURRENCE-ID;TZID=Europe/Brussels:20260914T090000',
            'DTSTART;TZID=Europe/Brussels:20260914T110000',
            'DTEND;TZID=Europe/Brussels:20260914T120000',
            'SUMMARY:Moved maintenance',
        ),
    ))

    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 9, 30, tzinfo=TZ)
    ) is None
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 11, 30, tzinfo=TZ)
    )['summary'] == 'Moved maintenance'


def test_failed_refresh_keeps_cache_and_hides_url(monkeypatch, caplog):
    secret_url = 'https://calendar.example/very-secret-token/calendar.ics'
    responses = iter([
        Response(ics(event(
            'UID:cached@example.com',
            'DTSTART;VALUE=DATE:20260914',
            'SUMMARY:Cached closure',
        ))),
        requests.Timeout(secret_url),
    ])

    def get(*_args, **_kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(calendar_module.requests, 'get', get)
    calendar = DisableCalendar(
        secret_url,
        timezone='Europe/Brussels',
        logger=logging.getLogger('calendar-cache-test'),
    )
    with caplog.at_level(logging.DEBUG):
        assert calendar.refresh() is True
        assert calendar.refresh() is False

    assert calendar.available is True
    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 12, tzinfo=TZ)
    )['summary'] == 'Cached closure'
    assert secret_url not in caplog.text
    assert 'using cached calendar data' in caplog.text


@pytest.mark.parametrize('failure', [Response(b'not an ics'), Response(b'', 500)])
def test_invalid_or_network_response_without_cache_enables_bells(
    monkeypatch, caplog, failure
):
    monkeypatch.setattr(
        calendar_module.requests, 'get', lambda *_args, **_kwargs: failure
    )
    calendar = DisableCalendar(
        'https://calendar.example/token/calendar.ics',
        logger=logging.getLogger('calendar-no-cache-test'),
    )

    with caplog.at_level(logging.WARNING):
        assert calendar.refresh() is False

    assert calendar.available is False
    assert calendar.blocking_event() is None
    assert 'Bells remain enabled' in caplog.text


def test_cancelled_standalone_event_is_ignored(monkeypatch):
    calendar = calendar_with(monkeypatch, ics(event(
        'UID:cancelled@example.com',
        'DTSTART;VALUE=DATE:20260914',
        'DTEND;VALUE=DATE:20260915',
        'STATUS:CANCELLED',
        'SUMMARY:Cancelled',
    )))

    assert calendar.blocking_event(
        datetime.datetime(2026, 9, 14, 12, tzinfo=TZ)
    ) is None
