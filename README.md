James II: Your Butler
=====================

James your Butler brought to the next level.

The Idea behing James Butler is to implement smarthome features in combination with multimedia to your existing infrastraucture.


ATTENTION: This project is under heavy dev and this readme is probably outdated.
---------------------------

ToDo:
------
Main:
* add process monitor / events
* log class

Plugins:
* plugin requirement checks before load
* HTTP monitor/plugin

You Need (outdated!):
---------
* python
* python-pika (https://github.com/pika/pika)
* python-psutil (http://code.google.com/p/psutil/)
* python-tz
* python-yaml
* python-requests (http://docs.python-requests.org/en/latest/index.html)
* python-transmissionrpc (https://bitbucket.org/blueluna/transmissionrpc/wiki/Home)
* python-jsonrpclib (https://github.com/joshmarshall/jsonrpclib/)


How to integrate JamesII torrent download to your linux desktop:
---------
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

RabbitMQueue Setup (also outdated!):
-------------
<pre><code>
apt-get  install rabbitmq-server
rabbitmqctl add_user test test
rabbitmqctl add_vhost test
rabbitmqctl set_permissions -p test test ".*" ".*" ".*"
</code></pre>

Technologies and software used (you guessed it: outdated!):
------------------
* XMPP http://en.wikipedia.org/wiki/Extensible_Messaging_and_Presence_Protocol
* AMQP http://en.wikipedia.org/wiki/AMQP
* Motion http://www.lavrsen.dk/foswiki/bin/view/Motion/WebHome
* eSpeak http://espeak.sourceforge.net/
* MPD http://mpd.wikia.com/wiki/Music_Player_Daemon_Wik
* Transmission http://www.transmissionbt.com/
* XBMC Mediacenter http://wiki.xbmc.org/
* Raspberry Pi http://www.raspberrypi.org/


Copy of the old Readme due lazyness:
------------------------------------

What he does:
* Monitors your LAN for unknown MAC addresses
* Monitors your home with motion when you are not at home
* Alerts events
* Speak via espeak
* Send XMPP (Jabber) messages (xmpp alert)
* Listens to XMPP commands (james bot)

Installation:
default installation dir: /opt/james

copy and edit:
- settings/james.cfg.example to settings/james.cfg
- settings/settings.sh.example to settings/settings.sh

add the watchdogs to crontab -e:
* * * * * /opt/james/new_event.sh periodic >/dev/null 2>&1


Attention:
* Theese are very "hacky" scripts. They should run as root but be aware of possible security risks!
* You should use different users for james (XMPP bot) and the alerting.
* You have to install (debian) python-xmp, screen, espeak, etherwake, rsync, nmap, arp-scan, sendxmpp, php, motion
* Optional: mpc

Based on:
* https://github.com/oxivanisher/beaglebot which is based on jabberbot
* mac2vendor - lookup the OUI part of a MAC address in the IEEE registration Hessel Schut, hessel@isquared.nl, 2008-10-12
* http://gentoo-wiki.com/Talk:TIP_Bluetooth_Proximity_Monitor
