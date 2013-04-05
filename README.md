James II: Your Butler brought to the next level.
=====================

The Idea behind JamesII Butler is to implement smarthome features in combination with multimedia, networking and interactive applications to your existing infrastructure. It consists of distributed python nodes which connect via a RabbitMQ server to talk to each other. There is one core node which hosts the configuration and some basic features.
The system is also very handy in combination with RaspberryPi's (http://www.raspberrypi.org/).
Module documentation nightly updated: http://oxi.ch/JamesII/

Things / Services you can use or interact with:
--------------
* CLI (managed) interface with history and command completion
* Cron (autoload on core node) which emulates a standard Unix like cron daemon
* Dbus-Notify (passive) as a messaging front-end
* Espeak (managed) as a messaging front-end and some commands
* Jabber (managed) as a messaging front-end and interface (has also MUC support)
* Monitor (managed) to show what is going on in the console
* Motion (managed) to watch over your home and also to automatically start webradio when you get up on weekends
* Mpd-Client (managed) to start/stop internet radios on different occasions (can also fade in and out for gn8 or wakeup)
* Proximity (managed) to scan the area for known bluetooth mac addresses
* Raspberry (managed) interactive interface with buttons/switches and LEDs to interact with the real world
* Sysstat (autoload) to request information's about the host like mounts, net info, memory info, ...
* System (autoload) james system calls mostly used internally
* Timer (autoload on core node) the all mighty MCP to time commands with "in" and "at"
* Transmission (managed) to add/remove/start/stop torrent downloads on a transmission server
* Wakeonlan (managed) to wake up devices when you come home for example
* Xbmc (managed) to trigger database updates and display onscreen messages (messages not tested and only xbmc 12 (frodo)!)

Plugin modes explanation:
* Manual: Passive plugins are run exclusively, normally with a separate bash command
* Managed: Only loaded if specified in config
* Autoload: If all requirements are met, this plugin will be loaded automatically

Core functionality:
--------------
* Integrated help. Just type help in interfaces
* Command aliases like "in 10m nom" which in fact will do "mcp in 10m espeak say nom nom nom nom nom"
* Logger facility with network functionality (netlog_monitor.py)

Not yet done:
* HTTP Server (managed) (As front-end, console and also RESTful API for mobile clients)
* Lirc (managed) to control or be controlled via infrared
* YAML Schema to detect wrong config files
* Doorbell extension for RaspberryPi Plugin
* plugin requirement checks before load for external files
* Monitor LAN for unknown MAC addresses, MAC address db (see old james)

You Need (debian packages):
---------
* python
* python-pika (https://github.com/pika/pika)
* python-psutil (sysstat plugin, http://code.google.com/p/psutil/)
* python-tz
* python-yaml
* screen (always a good idea)
<code>apt-get install python-pika python-psutil python-tz python-yaml</code>

Optional (plugin specific):
----------
* bluetooth (proximity plugin)
* espeak (espeak plugin)
* motion (motion plugin)
* python-mpd2 (mpd plugin)
* python-xmpp (jabber plugin)
* python-dbus (dbus notification plugin)
* python-transmissionrpc (transmission plugin, https://bitbucket.org/blueluna/transmissionrpc/wiki/Home)
* python-jsonrpclib (xbmc plugin, https://github.com/joshmarshall/jsonrpclib/)
* python-pylirc (lirc plugin, http://aron.ws/projects/lirc_rpi/)
<pre><code>apt-get install bluetooth espeak motion python-mpd2 python-xmpp python-dbus python-transmissionrpc python-pylirc python-pip 
pip install jsonrpclib</code></pre>

Installation and RabbitMQueue Setup:
-------------
* Clone JamesII to a directory (git clone git://github.com/oxivanisher/JamesII.git)
* Edit your config file (config/config.yaml)
* Install RabbitMQ
<pre><code>
apt-get  install rabbitmq-server
</code>
JamesII currently only uses anonymous rabbitmq auth. This following code is currently not needed.
<code>
rabbitmqctl add_user test test
rabbitmqctl add_vhost test
rabbitmqctl set_permissions -p test test ".*" ".*" ".*"
</code></pre>
* Start it with the james_loop.sh script as a user with sudo rights in a screen. Dirty, i know! But some plugins need root access to work.
<code>visudo: youruser ALL=(ALL) NOPASSWD: ALL</code>

How to integrate JamesII to your infrastructure:
---------
Desktop torrent download:
<pre>
$ sudo vim /usr/share/applications/JamesII.desktop
<code>
[Desktop Entry]
Exec=/path/to/JamesII/src/cli.sh tr add %U
MimeType=application/x-bittorrent;x-scheme-handler/magnet;
Terminal=false
Type=Application
</code>
$ xdg-mime default JamesII.desktop x-scheme-handler/magnet
</pre>

Desktop DBUS Notifications:
<pre><code>start the dbus-notify_loop.sh with your desktop</code></pre>

RaspberryPi Plugin:
<pre>
My prototype for the GPIO is working, but a real prototype. A schematic will follow sometimes.
<code>Checkout and read (!) include/install_wiring_pi.sh</code>
</pre>

Motion Plugin:
<pre><code>Add the following lines to your /etc/motion/motion.conf:
on_picture_save "/path/to/JamesII/src/cli.sh motion img %f"
on_movie_end "/path/to/JamesII/src/cli.sh motion mov %f"
on_camera_lost "/path/to/JamesII/src/cli.sh motion cam_lost"
</code></pre>

Technologies and software used (incomplete!):
------------------
* XMPP http://en.wikipedia.org/wiki/Extensible_Messaging_and_Presence_Protocol
* AMQP http://en.wikipedia.org/wiki/AMQP
* Motion http://www.lavrsen.dk/foswiki/bin/view/Motion/WebHome
* eSpeak http://espeak.sourceforge.net/
* MPD http://mpd.wikia.com/wiki/Music_Player_Daemon_Wik
* Transmission http://www.transmissionbt.com/
* XBMC Mediacenter http://wiki.xbmc.org/
* Raspberry Pi http://www.raspberrypi.org/

Thanks:
-----------------
Special thanks go to:
* http://github.com/westlicht for a lot of OO and Python knowledge
* http://aron.ws/projects/lirc_rpi/ for the IR solution used with RaspberryPi
* Kurt Fierz and Anaxagoras for support with the electronics part of JamesII (RaspberryPi plugin)
* https://github.com/tervor for alpha testing :)