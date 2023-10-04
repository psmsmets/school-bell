********************************
Configure alsa on a Raspberry Pi
********************************


Edit ``/etc/asound.conf``


Two mono zones:

.. code-block:: sh

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


Mono out (for both left and right):

.. code-block:: sh

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


Split the 8-channel outputs of the ESI GIGAPORT eX to multiple stereo PCM devices

.. code-block:: sh

    pcm.Gigaport {
      type hw
      card eX
    }

    ctr.Gigaport {
      type hw
      card eX
    }

    pcm.zones {
       type dmix
       ipc_key 673138
       ipc_key_add_uid false
       ipc_perm 0666
       slave {
           pcm "hw:1,0"
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
      slave {
        pcm "zones"
        channels 8
      }
      ttable.0.0 1
      ttable.1.1 1
    }

    pcm.zone2 {
      type plug
      slave {
        pcm "zones"
        channels 8
      }
      ttable.0.2 1
      ttable.1.3 1
    }

    pcm.zone3 {
      type plug
      slave {
        pcm "zones"
        channels 8
      }
      ttable.0.4 1
      ttable.1.5 1
    }

    pcm.zone4 {
      type plug
      slave {
        pcm "zones"
        channels 8
      }
      ttable.0.6 1
      ttable.1.7 1
    }

    pcm.!default {
      type plug
      slave.pcm "zone1"
    }

    ctl.!default {
      type hw
      card 0
    }
