#!/usr/bin/python3

"""Public iCalendar based bell suppression."""

import datetime
from threading import RLock
from urllib.parse import urlsplit

import pytz
import recurring_ical_events
import requests
from icalendar import Calendar


__all__ = ['DisableCalendar']


class DisableCalendar(object):
    """Fetch a public calendar and find events covering a local moment."""

    def __init__(
        self,
        url: str,
        timezone: str = 'Europe/Brussels',
        timeout: int = 10,
        logger=None,
    ):
        if not isinstance(url, str) or not url.strip():
            raise TypeError('disable_calendar should be a non-empty string!')
        if urlsplit(url).scheme.lower() not in ('http', 'https'):
            raise ValueError('disable_calendar should use HTTP or HTTPS!')

        self.__url = url
        self.__timezone = pytz.timezone(timezone)
        self.__timeout = int(timeout)
        self.__logger = logger
        self.__calendar = None
        self.__last_update = None
        self.__lock = RLock()

    @property
    def last_update(self):
        """Return the last successful refresh time."""
        with self.__lock:
            return self.__last_update

    @property
    def available(self) -> bool:
        """Return whether a successfully parsed calendar is cached."""
        with self.__lock:
            return self.__calendar is not None

    def refresh(self) -> bool:
        """Refresh the calendar, retaining the previous cache on failure."""
        try:
            response = requests.get(self.__url, timeout=self.__timeout)
            response.raise_for_status()
            calendar = Calendar.from_ical(response.content)
            if getattr(calendar, 'name', None) != 'VCALENDAR':
                raise ValueError('response is not an iCalendar calendar')
        except Exception as err:
            # Request exception strings often contain the complete secret URL.
            if self.__logger:
                if self.available:
                    self.__logger.warning(
                        'Public calendar refresh failed; using cached '
                        'calendar data.'
                    )
                else:
                    self.__logger.warning(
                        'Public calendar refresh failed; no cached calendar '
                        'data available. Bells remain enabled.'
                    )
                self.__logger.debug(
                    'Public calendar failure category: %s',
                    type(err).__name__,
                )
            return False

        with self.__lock:
            self.__calendar = calendar
            self.__last_update = datetime.datetime.now(
                datetime.timezone.utc
            )
        if self.__logger:
            self.__logger.info('Public calendar refreshed successfully.')
        return True

    def blocking_event(self, moment: datetime.datetime = None):
        """Return event details when an occurrence covers ``moment``."""
        moment = self._local_datetime(moment)
        with self.__lock:
            calendar = self.__calendar
        if calendar is None:
            return None

        try:
            occurrences = recurring_ical_events.of(calendar).between(
                moment,
                moment + datetime.timedelta(microseconds=1),
            )
        except Exception as err:
            if self.__logger:
                self.__logger.warning(
                    'Public calendar data could not be evaluated; bells '
                    'remain enabled.'
                )
                self.__logger.debug(
                    'Public calendar evaluation failure category: %s',
                    type(err).__name__,
                )
            return None

        for event in occurrences:
            if str(event.get('STATUS', '')).upper() == 'CANCELLED':
                continue
            interval = self._event_interval(event)
            if interval is None:
                continue
            start, end, all_day = interval
            if start <= moment < end:
                return {
                    'summary': str(event.get('SUMMARY', 'Untitled event')),
                    'start': start,
                    'end': end,
                    'all_day': all_day,
                }
        return None

    def _event_interval(self, event):
        """Convert one expanded VEVENT to a local half-open interval."""
        start_property = event.get('DTSTART')
        if start_property is None:
            return None
        start_value = start_property.dt
        all_day = isinstance(start_value, datetime.date) and not isinstance(
            start_value, datetime.datetime
        )

        end_property = event.get('DTEND')
        if end_property is not None:
            end_value = end_property.dt
        elif event.get('DURATION') is not None:
            end_value = start_value + event.get('DURATION').dt
        elif all_day:
            end_value = start_value + datetime.timedelta(days=1)
        else:
            # RFC 5545 gives DATE-TIME events without an end zero duration.
            end_value = start_value

        start = self._local_datetime(start_value, all_day=all_day)
        end = self._local_datetime(end_value, all_day=all_day)
        return start, end, all_day

    def _local_datetime(self, value=None, all_day=False):
        """Normalize dates, floating times and aware times to local time."""
        if value is None:
            return datetime.datetime.now(self.__timezone)
        if all_day or (
            isinstance(value, datetime.date) and
            not isinstance(value, datetime.datetime)
        ):
            return self.__timezone.localize(
                datetime.datetime.combine(value, datetime.time.min)
            )
        if value.tzinfo is None:
            return self.__timezone.localize(value)
        return value.astimezone(self.__timezone)
