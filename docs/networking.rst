Networking and time synchronization
===================================

Network dependencies
--------------------

Scheduled ringing itself uses local state. Network access is needed only for
features that have been configured or for administrative operations:

* installation, updates and Ansible deployment;
* NTP time synchronization;
* OpenHolidays and iCalendar refreshes;
* remote syslog and HTTP status checks;
* SSH or webhook bell triggers.

Firewall rules should allow only the required outbound destinations and
explicitly authorized inbound status or webhook traffic. The built-in HTTP
servers do not provide TLS; bind them to a trusted interface or localhost and
place a TLS reverse proxy in front of them. See :ref:`expose-bell-webhook` for
a local HTTPS example with Caddy.

For direct webhook traffic on a trusted LAN, a stable local IP address avoids
hostname or mDNS lookup latency. Hostnames are easier to maintain when devices
are renumbered, but require reliable local DNS. This choice affects connection
setup only; it does not change how long the receiving endpoint takes to reply.

Time synchronization
--------------------

Accurate system time is a runtime requirement. Each node should synchronize
with either:

* reliable online NTP servers; or
* one or more local NTP servers on the site's network.

A local NTP server is preferable where internet access is restricted or where
all bells must follow the same time source. Configure more than one source when
the infrastructure permits it.

Verify synchronization with:

.. code-block:: console

   timedatectl status
   timedatectl timesync-status

The configured School Bell timezone affects interpretation of the schedule;
NTP itself synchronizes the underlying clock independently of that timezone.

Temporary outages
-----------------

============================  ================================================
Unavailable component         Expected behavior
============================  ================================================
Ansible/controller            The last locally loaded schedule keeps running.
Graylog/syslog                 Local ringing continues; events may be lost.
Status client                 The scheduler does not require status polling.
OpenHolidays                  Local scheduling remains available; holiday data
                              may not refresh.
iCalendar source              Cached in-memory data is retained after a failed
                              refresh. Without cached data, bells remain
                              enabled.
Remote SSH/webhook target     The remote action can fail without changing the
                              associated local manual bell result.
Online NTP                    The system clock continues running but may drift;
                              a local NTP source can avoid this dependency.
============================  ================================================

Clock failure limitations
-------------------------

Temporary NTP loss does not stop the process, but scheduling accuracy depends
on the host clock. After a reboot without reachable NTP, a Raspberry Pi without
a reliable real-time clock may start with an incorrect time. School Bell does
not currently block startup until synchronization is confirmed and cannot
guarantee correct ringing in that state.

Monitor synchronization at the infrastructure level and alert on excessive
clock offset. Consider a battery-backed RTC and local NTP for sites where exact
operation must survive internet and power disruptions.

Missed scheduled jobs are not replayed after downtime or a corrected clock.
