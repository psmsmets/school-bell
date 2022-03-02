*************************************
Configure a Raspberry Pi from scratch
*************************************

Prepare
=======

Use `Rapberry Pi Imager`__ to install *Raspberry Pi OS Lite (32-bit)* on an microSD card (16GB class 10 is fine).

.. __: https://www.raspberrypi.org/blog/raspberry-pi-imager-imaging-utility/

Use the configuration tool to

* enable ssh on boot
* connect to your wireless network
* set the username and password


Connect
=======

Connect to the Raspberry Pi via `ssh`.

.. code-block:: sh

    ssh pi@raspberrypi.local

The default credentials are `pi` and `raspberry`.


Configure
=========

Core configuration

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


Install Python core packages (apt)

.. code-block:: sh

    sudo apt update
    sudo apt install -y libatlas-base-dev
    sudo apt install -y build-essential libssl-dev libffi-dev
    sudo apt install -y python3 python3-pip python3-dev python3-venv python3-setuptools
    sudo apt install -y python3-numpy python3-gpiozero python3-serial


Create and activate the Python venv

.. code-block:: sh

    /usr/bin/python3 -m venv --clear --prompt py3 ~/.local
    source /home/pi/.local/bin/activate


Upgrade pip and install related packages in venv

.. code-block:: sh

    pip install --upgrade pip setuptools setuptools_scm wheel


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
