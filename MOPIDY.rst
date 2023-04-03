******************************
Setup Mopidy on a Raspberry Pi
******************************

Install Mopidy for Debian/Ubuntu:
=================================

Checkout `Install from apt.mopidy.com`__ to install *Mopidy*.

.. __: hhttps://docs.mopidy.com/en/latest/installation/debian/#install-from-apt-mopidy-com


Installing extensions:
======================

.. code-block:: sh

    # Mopidy-Iris
    sudo python3 -m pip install Mopidy-Iris
     
    # Mopidy-Spotify
    git clone https://github.com/beaverking1212/mopidy-spotify
    cd mopidy-spotify
    sudo python3 -m pip install .
    
    # Mopidy-TuneIn
    sudo apt install mopidy-tunein
    
    # Mopidy-YouTube
    sudo apt-get install gstreamer1.0-plugins-bad
    sudo python3 -m pip install -U yt-dlp
    sudo python3 -m pip install Mopidy-YouTube
    
Configure alsa:
===============

Edit `/etc/.conf`

.. code-block:: sh

    ...

Configure mopidy:
=================

Edit `/etc/mopidy/mopidy.conf`

.. code-block:: sh

    [audio]
    # mixer_volume = 50
    output = alsasink device=hw:0,0
    
    [core]
    restore_state = true

    [http]
    enabled = true
    hostname = mopidy.local
    port = 6680
    default_app = iris

    [iris]
    country = be
    locale = nl_BE
    snapcast_enabled = false
    
    [spotify]
    # https://github.com/beaverking1212/mopidy-spotify
    enabled = true
    username = alice
    password = secret
    client_id = ... client_id value you got from mopidy.com ...
    client_secret = ... client_secret value you got from mopidy.com ...

    [stream]
    enabled = true
    protocols =
        http
        https
        mms
        rtmp
        rtmps
        rtsp
    timeout = 5000
    metadata_blacklist =
    
    [tunein]
    enabled = true
    timeout = 5000
    filter = station

    [youtube]
    # https://github.com/natumbri/mopidy-youtube
    enabled = true
    youtube_dl_package = "yt-dlp"
    allow_cache = false
    autoplay_enabled = false
    
Restart mopidy service after update

.. code-block:: sh

    sudo systemctl restart mopidy
