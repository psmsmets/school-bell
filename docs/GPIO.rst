GPIO, relays and manual button
==============================

School Bell can switch one or more relay outputs while a sound is playing. An
optional push button can start a manual bell signal. Audio-only installations
do not need GPIO configuration.

This page uses Raspberry Pi GPIO terminology. GPIO pins provide logic signals;
they must not power a bell, amplifier, relay coil or mains-voltage circuit
directly. Use a suitable relay interface with electrical isolation and have
fixed or high-voltage wiring installed by a qualified person.

Understanding pin numbers
-------------------------

All GPIO numbers in ``config.json`` are **BCM GPIO numbers**. They are not the
physical header positions and not wiringPi numbers. For example, BCM GPIO 17 is
physical header pin 11.

Check the header diagram for the exact Raspberry Pi model before connecting
anything. The `Raspberry Pi GPIO Pinout`_ shows BCM numbers, physical pins,
power and ground pins together. Never select a 3.3 V, 5 V or ground pin as a
GPIO number merely because its physical header position has that number.

.. _Raspberry Pi GPIO Pinout: https://pinout.xyz/

Relay outputs
-------------

``buzz_gpio`` accepts one BCM GPIO number or a list. With multiple entries all
configured relays switch together while the bell signal is playing:

.. code-block:: json

   {
     "buzz_gpio": 17
   }

.. code-block:: json

   {
     "buzz_gpio": [26, 20, 21],
     "buzz_active_high": false
   }

``buzz_active_high`` describes the relay input:

* ``true`` (the default) drives an output high to ring;
* ``false`` drives an output low to ring and is required for active-low boards.

School Bell initializes every output to its configured inactive state and
returns it to that state after ringing. Confirm the polarity for the actual
relay board before connecting the bell circuit; the wrong value can energize a
relay as soon as the software starts.

Waveshare RPi Relay Board
~~~~~~~~~~~~~~~~~~~~~~~~~

The three channels of the `Waveshare RPi Relay Board`_ use these values:

.. list-table::
   :header-rows: 1
   :widths: 25 25 30

   * - Relay channel
     - BCM GPIO
     - Label printed on board
   * - 1
     - 26
     - P25
   * - 2
     - 20
     - P28
   * - 3
     - 21
     - P29

The printed P25, P28 and P29 labels use wiringPi numbering. Put the BCM values
``26``, ``20`` and ``21`` in the School Bell configuration. This board has
active-low inputs, so configure ``"buzz_active_high": false``.

Consult the board manufacturer's documentation as well. Revisions or other
relay boards can use different pins and polarity.

.. _Waveshare RPi Relay Board: https://www.waveshare.com/wiki/RPi_Relay_Board

Connect the bell circuit safely
-------------------------------

For fail-safe switching, normally connect the external bell circuit through
the relay's ``COM`` (common) and ``NO`` (normally open) contacts. The circuit
then remains open when the relay is not energized. Do not use ``NC`` (normally
closed) unless that behavior has been deliberately designed and assessed.

Software polarity alone cannot guarantee a safe state during boot, shutdown,
loss of Pi power or an unpowered relay input. Before connecting the real bell:

#. disconnect the external bell or high-voltage circuit;
#. verify the GPIO number and active-high/active-low setting;
#. measure or observe the relay contacts while booting, ringing and shutting
   down;
#. confirm that ``COM`` and ``NO`` are disconnected whenever the bell should be
   silent;
#. only then connect the external circuit.

Manual push button
------------------

``manual_bell`` assigns a BCM GPIO input to a physical momentary push button:

.. code-block:: json

   {
     "manual_bell": {
       "gpio": 17,
       "wav_key": "0",
       "mode": "once",
       "pull": "up",
       "bounce_time": 0.05
     }
   }

With the default ``"pull": "up"``, connect the button between the configured
GPIO input and a ground pin. The internal pull-up keeps the input high while
the button is open; pressing it connects the input to ground. ``pull`` can also
be ``down`` or ``floating`` for hardware designed that way. A floating input
requires a suitable external resistor and should not be left electrically
unconnected.

The input pin must not also occur in ``buzz_gpio``. ``bounce_time`` filters
short contact bounce after pressing the button. In ``once`` mode one press
finishes the selected sound; in ``hold`` mode releasing the button stops it,
with the sample duration as the maximum.

Manual signals are deliberate overrides and are not suppressed by holiday or
disable calendars. Only one bell signal can run at a time. See
:doc:`configuration-reference` for remote SSH and webhook actions that can be
attached to the button.

Test before commissioning
-------------------------

First validate configuration and files without operating the hardware:

.. code-block:: console

   $ school-bell /home/pi/schema.json --check

Then disconnect the real bell circuit and run the hardware test:

.. code-block:: console

   $ school-bell /home/pi/schema.json --test

``--test`` activates each configured ``buzz_gpio`` output sequentially for one
second and returns it to the inactive state before testing the next output. It
also tests the configured WAVE samples, so keep audio at a safe level.

If an output does not behave as expected, stop and check the BCM number, relay
polarity, board power, connections and service-user permissions. Continue with
:doc:`troubleshooting` only while the external bell circuit remains safely
disconnected.
