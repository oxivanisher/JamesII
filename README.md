# James II: Your Butler brought to the next level.
The Idea behind JamesII Butler is to implement smarthome features in combination with multimedia, networking and interactive applications to your existing infrastructure. It consists of distributed python nodes which connect via a RabbitMQ server to talk to each other. There is one core node which hosts the configuration and some basic features.
The system is also very handy in combination with RaspberryPi's (http://www.raspberrypi.org/).
Module documentation nightly updated: http://oxi.ch/JamesII/

## Things / Services you can use or interact with:
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
* LIRC (managed) to control or be controlled by IR devices

#### Plugin modes explanation:
* Manual: Passive plugins are run exclusively, normally with a separate bash command
* Managed: Only loaded if specified in config
* Autoload: If all requirements are met, this plugin will be loaded automatically

### Core functionality:
* Integrated help. Just type help in interfaces
* Command aliases like "in 10m nom" which in fact will do "mcp in 10m espeak say nom nom nom nom nom"
* Logger facility with network functionality who also can log to mysql (netlogger.py)
* @hostname1,hostname2 for running commands only on choosen host(s)
* && to split commands (will not wait for the first command to exit, will send them right after each other)

### Not yet done:
* HTTP Server (managed) (As front-end, console and also RESTful API for mobile clients)
* YAML Schema to detect wrong config files
* Doorbell extension for RaspberryPi Plugin
* plugin requirement checks before load for external files
* Monitor LAN for unknown MAC addresses, MAC address db (see old james)

## You Need:
* python
* python-pika (https://github.com/pika/pika)
* python-psutil (sysstat plugin, http://code.google.com/p/psutil/)
* python-tz
* python-yaml
* screen (always handy)

#### Debian/Ubuntu:
	apt-get install python-yaml python-pika python-psutil python-tz

#### OS X (Mac Ports):
	sudo port select --set python python27
	sudo port install py27-yaml py27-pika py27-psutil py27-pip
	sudo pip-2.7 install pytz

### Optional (Plugin specific):
* bluetooth (proximity plugin)
* espeak (espeak plugin)
* motion (motion plugin)
* python-mpd2 (mpd plugin)
* python-xmpp (jabber plugin)
* python-dbus (dbus notification plugin)
* python-transmissionrpc (transmission plugin, https://bitbucket.org/blueluna/transmissionrpc/wiki/Home)
* python-jsonrpclib (xbmc plugin, https://github.com/joshmarshall/jsonrpclib/)
* python-pylirc (lirc plugin, http://aron.ws/projects/lirc_rpi/)

#### Debian/Ubuntu:
	apt-get install bluetooth espeak motion python-xmpp python-dbus \
	python-transmissionrpc python-pylirc python-pip
	pip install jsonrpclib python-mpd2

## Installation:
* Clone JamesII to a directory as user "youruser"

	git clone git://github.com/oxivanisher/JamesII.git

* Edit your main config file only on master node ([config/config.yaml.example](https://github.com/oxivanisher/JamesII/blob/master/config/config.yaml.example "Base Config Example"))
* Edit your broker config file on every node ([config/broker.yaml.example](https://github.com/oxivanisher/JamesII/blob/master/config/broker.yaml.example "Broker Example"))

## RabbitMQ Server Setup:
You only need one server per network. This server does not need a JamesII node.
* Install RabbitMQ as root (Debian/Ubuntu):
	apt-get install rabbitmq-server
* Then you have to configure your rabbitmq server as root and choose a password for the broker.yaml config:

	<pre>rabbitmqctl add_user james2 password
	rabbitmqctl add_vhost james2
	rabbitmqctl set_permissions -p james2 james2 ".*" ".*" ".*"</pre>

### Autostart on Linux:
* Starting it with the james2_autostart_loop.sh script as a user with sudo rights in a screen. Dirty, i know! But some plugins need root access to fully work. Here is how to give the user the needed rights via "visudo" as root:

	youruser ALL=(ALL) NOPASSWD: ALL
* To start JamesII automatically with your system, add the following line to /etc/rc.local before the "exit 0" line:

	su -c /path/to/JamesII/james2_autostart_loop.sh youruser &

### How to integrate JamesII to your infrastructure:
#### Desktop torrent download:
	$ sudo vim /usr/share/applications/JamesII.desktop

	[Desktop Entry]
	Exec=/path/to/JamesII/src/cli.sh tr add %U
	MimeType=application/x-bittorrent;x-scheme-handler/magnet;
	Terminal=false
	Type=Application

	$ xdg-mime default JamesII.desktop x-scheme-handler/magnet

#### Desktop DBUS Notifications:
	start the dbus-notify_loop.sh with your desktop

#### Motion Plugin:
After setting up motion, add the following lines to your /etc/motion/motion.conf:

	on_picture_save "/path/to/JamesII/src/cli.sh motion img %f"
	on_movie_end "/path/to/JamesII/src/cli.sh motion mov %f"
	on_camera_lost "/path/to/JamesII/src/cli.sh motion cam_lost"

#### RaspberryPi Plugin:

	My prototype for the GPIO is working, but is a real prototype. A schematic will follow sometimes.
	Checkout and read (!) include/install_wiring_pi.sh

## Technologies and software used (incomplete!):
* XMPP http://en.wikipedia.org/wiki/Extensible_Messaging_and_Presence_Protocol
* AMQP http://en.wikipedia.org/wiki/AMQP
* Motion http://www.lavrsen.dk/foswiki/bin/view/Motion/WebHome
* eSpeak http://espeak.sourceforge.net/
* MPD http://mpd.wikia.com/wiki/Music_Player_Daemon_Wik
* Transmission http://www.transmissionbt.com/
* XBMC Mediacenter http://wiki.xbmc.org/
* Raspberry Pi http://www.raspberrypi.org/

## Thanks go to:
* http://github.com/westlicht for a lot of OO and Python knowledge
* http://aron.ws/projects/lirc_rpi/ for the IR solution used with RaspberryPi
* Kurt Fierz and Anaxagoras for support with the electronics part of JamesII (RaspberryPi plugin)
* https://github.com/tervor for alpha testing :)