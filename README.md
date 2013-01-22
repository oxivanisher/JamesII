James II: Your Butler
=====================

James your Butler brought to the next level.

The Idea behing JamesII Butler is to implement smarthome features in combination with multimedia, networking and interaction applications to your existing infrastraucture.

Module documentation nightly updated: http://oxi.ch/JamesII/doc/

ToDo:
------
Main:
* log class
* YAML Schemas to detect wrong config files

Plugins:
* LIRC plugin for RaspberryPi (http://aron.ws/projects/lirc_rpi/)
* Doorbell extension for RaspberryPi Plugin
* plugin requirement checks before load (external files)
* HTTP monitor/plugin with restapi for future mobile apps
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
* mpc, mpdtoys (mpd plugin)
* python-xmpp (jabber plugin)
* python-dbus (dbus notification plugin)
* python-transmissionrpc (transmission plugin, https://bitbucket.org/blueluna/transmissionrpc/wiki/Home)
* python-jsonrpclib (xbmc plugin, https://github.com/joshmarshall/jsonrpclib/)
* python-pylirc (lirc plugin)
<pre><code>apt-get install bluetooth espeak motion mpc mpdtoys python-xmpp python-dbus python-transmissionrpc python-pylirc python-pip
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
* Start it with the james_loop.sh script as a user with sudo rights in a screen. Dirty, i know! But some tools need root access to work.
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

Technologies and software used (probably outdated!):
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
* Kurt Fierz and Anaxagoras for support with the electronic part of JamesII