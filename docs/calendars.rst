Holidays and calendar exceptions
================================

School Bell can suppress **scheduled** signals on school or public holidays
and during events from a published iCalendar feed. These integrations are
optional: a basic local schedule does not require internet access.

Manual button, command-line and webhook signals are deliberate overrides. They
are not blocked by either calendar source. Test that distinction before using
manual signals in a production installation.

OpenHolidays
------------

Set ``holidays`` to an `OpenHolidays API`_ group code. For example, ``BE-NL``
selects the Dutch-language Belgian school-holiday group:

.. code-block:: json

   {
     "holidays": "BE-NL",
     "timeout": 10
   }

At startup School Bell requests public and school holidays for the next 180
days. It refreshes the data daily. A date returned as either kind of holiday
suppresses every scheduled signal on that date.

If OpenHolidays cannot be reached, School Bell logs a warning and continues
running. Previously downloaded data remains available in memory. When no
holiday data is available, scheduled bells remain enabled; connectivity loss
does not silently turn the central API into a runtime requirement.

Use the OpenHolidays `service status`_ when the local network works but holiday
requests fail.

.. _OpenHolidays API: https://www.openholidaysapi.org/en/api/
.. _service status: https://openpotato.github.io/uptime/

Public iCalendar feed
---------------------

``disable_calendar`` accepts a public HTTP(S) iCalendar (``.ics``) URL:

.. code-block:: json

   {
     "timezone": "Europe/Brussels",
     "disable_calendar": "https://example.com/private/calendar.ics",
     "timeout": 10
   }

Every non-cancelled event disables scheduled bells during its effective
period:

* an all-day event disables the complete local day;
* a timed event disables signals from its start until, but not including, its
  end;
* an event can span hours or several days;
* recurring events, excluded dates and modified occurrences are expanded;
* cancelled occurrences do not disable bells.

Times are evaluated in the configured School Bell timezone. Events containing
their own timezone are converted to it; floating times are interpreted as
local times. A date-only event starts at local midnight.

School Bell downloads the feed at startup and refreshes it every day at 00:05
in the configured timezone. After a failed refresh, the last successfully
parsed in-memory calendar is retained. If no valid feed has ever been loaded,
scheduled bells remain enabled and the failure is logged.

When structured monitoring is configured, successful OpenHolidays and
iCalendar loads emit ``calendar_refresh``. Fetch, parse and evaluation failures
emit ``calendar_error``. These events report cache availability and the last
successful update without including the configured iCalendar URL.

Publish a feed
--------------

Calendar providers use different wording for published feeds:

* in Google Calendar, find the public or secret iCal address under *Integrate
  calendar*;
* in Outlook, publish the calendar and copy the generated ICS link.

See the provider documentation for `Google Calendar sharing`_ and `Outlook
calendar publishing`_. Anyone who obtains a secret calendar URL may be able to
read its events. Limit the event details and sharing permissions, keep the URL
out of version control and do not paste it into logs or issue reports. School
Bell redacts this URL from its normal startup and validation errors.

.. _Google Calendar sharing: https://support.google.com/calendar/answer/37083
.. _Outlook calendar publishing: https://support.microsoft.com/office/share-your-calendar-in-outlook-on-the-web-7ecef8ae-139c-40d9-bae2-a23977ee58d5

Validate calendar access
------------------------

Run the non-destructive check as the service user:

.. code-block:: console

   $ /home/pi/.local/bin/school-bell /home/pi/schema.json --check

It validates the OpenHolidays response and parses the iCalendar feed without
starting the scheduler, playing audio, switching GPIO or starting listeners.
``OK`` confirms a successful check, ``NOT CONFIGURED`` is informational and an
``ERROR`` produces a non-zero exit status.

Test a temporary event around a scheduled time before relying on the feed.
Then test loss of network access: the node should keep running and use its
cached data as described above. See :doc:`networking` for the wider outage
model and :doc:`troubleshooting` for connection failures.
