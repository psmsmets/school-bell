******************************
Setup Mopidy on a Raspberry Pi
******************************

Install Mopidy for Debian/Ubuntu:
=================================

Checkout `Install from apt.mopidy.com`__ to install *Mopidy*.

.. __: https://docs.mopidy.com/en/latest/installation/debian/#install-from-apt-mopidy-com


Installing extensions:
======================

1. Mopidy

.. code-block:: sh

    # Mopidy-Autoplay
    sudo python3 -m pip install Mopidy-Autoplay

2. Mopidy-Iris

.. code-block:: sh

    # Mopidy-Iris
    sudo python3 -m pip install Mopidy-Iris
    sudo sh -c 'echo "mopidy  ALL=NOPASSWD:   /usr/local/lib/python3.9/dist-packages/mopidy_iris/system.sh" >> /etc/sudoers'

3. Mopidy-Spotify

.. code-block:: sh
     
    # Mopidy-Spotify
    sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gcc pkg-config git
    sudo curl --proto '=https' --tlsv1.2 --output /usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstspotify.so https://www.pietersmets.be/share/libgstspotify.so
    gst-inspect-1.0 spotify
    sudo python3 -m pip install git+https://github.com/mopidy/mopidy-spotify

4. Mopidy-TuneIn

.. code-block:: sh
    
    # Mopidy-TuneIn
    sudo apt install mopidy-tunein

5. Mopidy-Youtube

.. code-block:: sh
    
    # Mopidy-YouTube
    sudo apt-get install gstreamer1.0-plugins-bad
    sudo python3 -m pip install --upgrade youtube-dl yt-dlp
    sudo python3 -m pip install Mopidy-YouTube


Optional: compile gst-plugins-spotify from source

.. code-block::sh

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    sudo apt install libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev pkg-config git
    git clone --depth 1 https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs

    cd gst-plugins-rs
    cargo build --package gst-plugin-spotify --release -j1
    sudo install -m 644 target/release/libgstspotify.so $(pkg-config --variable=pluginsdir gstreamer-1.0)/


Configure mopidy:
=================

Edit ``/etc/mopidy/mopidy.conf``

.. code-block:: sh

    [mpd]
    enabled = true
    hostname = ::

    [http]
    # Make sure the web interface can be accessed by the local network
    hostname = 0.0.0.0
    port = 6680
    default_app = iris

    [audio]
    mixer_volume = 85
    output = alsasink device=speelplaats

    [iris]
    country = be
    locale = nl_BE
    snapcast_enabled = false

    [file]
    enabled = false

    [m3u]
    enabled = false

    [spotify]
    # https://github.com/beaverking1212/mopidy-spotify
    enabled = true
    username = alice
    password = secret
    client_id = ... client_id value you got from mopidy.com ...
    client_secret = ... client_secret value you got from mopidy.com ...

    [youtube]
    # https://github.com/natumbri/mopidy-youtube
    enabled = true
    youtube_dl_package = yt_dlp
    autoplay_enabled = false

    
Restart mopidy service after update

.. code-block:: sh

    sudo systemctl restart mopidy


Configure alsa:
===============

Edit ``/etc/asound.conf``

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
