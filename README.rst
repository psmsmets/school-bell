*************************************
School Bell
*************************************

Python scheduled ringing of the school bell

Configuration (json)
====================

.. code-block:: JSON

    {
        "schedule": {
            "Mon": ["08:30", "12:00", "15:00"],
            "Tue": ["08:30", "12:00", "15:00"],
            "Wed": ["08:30", "12:00"],
            "Thu": ["08:30", "12:00", "15:00"],
            "Fri": ["08:30", "12:00", "15:00"]
        },
        "trigger": {
            "pi@10.10.70.121": "aplay SchoolBell.wav &"
        },
        "wav": "SchoolBell-SoundBible.com-449398625.wav"
    }

Licensing
=========

The source code for school-bell is licensed under MIT that can be found under the LICENSE file.

Pieter Smets © 2022. All rights reserved.
