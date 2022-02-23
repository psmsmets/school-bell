*************************************
School Bell
*************************************

Python scheduled ringing of the school bell.

Installation
============

.. code-block:: bash

    pip install -e


Usage
=====

Type ``school-bell --help`` for the usage.


.. code-block::

    usage: school-bell [-h] [-a ..] [-b [..]] [-c ..] [--debug] [--version]

    Python scheduled ringing of the school bell.

    optional arguments:
      -h, --help            show this help message and exit
      -a .., --wav ..       WAV audio file
      -b [..], --buzz [..]  Buzz via RPi GPIO while the WAV audio file plays
      -c .., --config ..    JSON configuration file
      --debug               Make the operation a lot more talkative
      --version             Print the version and exit


Configuration (JSON)
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

The remote trigger requires an ``ssh-key`` to connect to the remote host!


Configure a clean RPi
=====================


.. code-block:: sh

    # upgrade existing packages
    sudo apt update
    sudo apt upgrade -y

    # install core packages
    sudo apt install -y git wget vim build-essential checkinstall

    # configure vim
    cat << EOF >> /home/$USER/.vimrc
    filetype plugin indent off
    syntax on
    set term=builtin_xterm
    set term=xterm-256color
    set number
    set mouse=r
    EOF

    # raspi-config
    sudo raspi-config nonint do_memory_split 16
    sudo raspi-config --expand-rootfs
    sudo raspi-config nonint do_hostname pibell
    sudo reboot


Install Python core packages

.. code-block:: sh

    sudo apt update
    sudo apt install -y libatlas-base-dev
    sudo apt install -y build-essential libssl-dev libffi-dev
    sudo apt install -y python3 python3-pip python3-dev python3-venv python3-setuptools
    sudo apt install -y python3-numpy python3-gpiozero python3-serial


Create and activate Python venv

.. code-block:: sh

    /usr/bin/python3 -m venv --clear --prompt py3 ~/.local
    source /home/pi/.local/bin/activate


Install Python packages in venv

.. code-block:: sh

    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install systemd
    pip install --upgrade setuptools_scm
    pip install --upgrade wheel


Add aliases and Python venv activation to ``~/.bashrc``

.. code-block:: sh

    cat << EOF >> /home/$USER/.bashrc
    # aliases
    alias ls='ls -h --color'
    alias l=ls
    alias ll='ls -l'
    alias la='ls -all'
    alias vi=vim
    alias status='systemctl status'
    alias start='sudo systemctl start'
    alias stop='sudo systemctl stop'
    alias restart='sudo systemctl restart'
    alias reset-failed='sudo systemctl reset-failed'

    # venv
    source /home/pi/.local/bin/activate
    EOF


Licensing
=========

The source code for school-bell is licensed under MIT that can be found under the LICENSE file.

Pieter Smets © 2022. All rights reserved.
