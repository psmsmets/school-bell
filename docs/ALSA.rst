Audio and ALSA
==============

School Bell uses ``aplay`` for WAVE playback on Linux. ALSA configuration is a
local runtime dependency: central connectivity is not involved once the audio
files and device configuration are present.

Discover devices
----------------

List physical cards and named playback devices:

.. code-block:: console

   aplay -l
   aplay -L

Test a sample directly before involving School Bell:

.. code-block:: console

   aplay /home/pi/samples/bell.wav
   aplay -D DEVICE /home/pi/samples/bell.wav

Set the working named device in JSON:

.. code-block:: json

   {
       "device": "DEVICE"
   }

Run ``school-bell schema.json --check`` to verify files without playing them,
or ``--test`` to exercise real playback and GPIO outputs. Use ``--test`` only
when ringing is safe.

Volume and permissions
----------------------

Inspect and adjust the mixer with ``alsamixer`` or ``amixer``. Confirm that
channels are not muted and that systemd runs School Bell as a user with access
to the audio device. Install ``alsa-utils`` and grant the service user the
required device access explicitly; the current Ansible initialization playbook
does not manage these audio-specific host settings.

Useful checks include:

.. code-block:: console

   groups pi
   amixer scontrols
   journalctl -u school-bell.service -n 100 --no-pager

Named PCM devices
-----------------

Define site-specific devices in ``/etc/asound.conf``. Test every definition
with ``aplay -D NAME`` before using it in configuration.

Two mono zones
~~~~~~~~~~~~~~

This example maps the left and right channels to separate named outputs:

.. code-block:: text

   pcm.output {
     type hw
     card 0
   }
   ctl.!default {
     type hw
     card 0
   }
   pcm.klas {
     type plug
     slave {
       pcm "output"
       channels 2
     }
     ttable.0.0 1
   }
   pcm.speelplaats {
     type plug
     slave {
       pcm "output"
       channels 2
     }
     ttable.0.1 1
   }

Mono on both channels
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   pcm.output {
     type hw
     card 0
   }
   ctl.!default {
     type hw
     card 0
   }
   pcm.mono {
     type plug
     slave {
       pcm "output"
       channels 2
     }
     ttable.0.0 1
     ttable.0.1 1
   }

Multi-channel USB interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following pattern splits an eight-channel ESI GIGAPORT eX into four stereo
PCM devices:

.. code-block:: text

   pcm.Gigaport {
     type hw
     card eX
   }
   ctl.Gigaport {
     type hw
     card eX
   }
   pcm.zones {
     type dmix
     ipc_key 673138
     ipc_key_add_uid false
     ipc_perm 0666
     slave {
       pcm "Gigaport"
       rate 48000
       period_time 0
       period_size 1024
       buffer_size 8192
       channels 8
     }
     bindings {
       0 0
       1 1
       2 2
       3 3
       4 4
       5 5
       6 6
       7 7
     }
   }
   pcm.zone1 {
     type plug
     slave { pcm "zones" channels 8 }
     ttable.0.0 1
     ttable.1.1 1
   }
   pcm.zone2 {
     type plug
     slave { pcm "zones" channels 8 }
     ttable.0.2 1
     ttable.1.3 1
   }
   pcm.zone3 {
     type plug
     slave { pcm "zones" channels 8 }
     ttable.0.4 1
     ttable.1.5 1
   }
   pcm.zone4 {
     type plug
     slave { pcm "zones" channels 8 }
     ttable.0.6 1
     ttable.1.7 1
   }
   pcm.!default {
     type plug
     slave.pcm "zone1"
   }

Select ``zone1`` through ``zone4`` with the top-level ``device`` setting.

Common failures
---------------

``audio open error`` or unknown PCM
   The configured name does not exist for the service user. Compare it with
   ``aplay -L`` and check ``/etc/asound.conf`` syntax.

``device busy``
   Another process owns an exclusive hardware device. Use an appropriate ALSA
   mixing PCM or stop the conflicting process.

Playback succeeds but is silent
   Check mixer mute state, physical cabling, selected output and sample format.

Works interactively but not under systemd
   Compare users, groups, environment and device names. Test ``aplay`` as the
   configured service user.
