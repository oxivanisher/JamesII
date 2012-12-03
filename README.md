James II: Your Butler
=====================

James your Butler brought to the next level.

The Idea behing James Butler is to implement smarthome functions and ideas to your existing infrastraucture like.


ATTENTION: This project is under heavy dev and this readme is probably outdated.
---------------------------

ToDo:
------
Main:
* centralized config management (config over rabbitmq)
* add process monitor / events
* add "discovery channel"
* add messaging channel with message types (warn, info, error)

Plugins:
* plugin requirement checks before load
* scripting plugin
* psutils plugin for system informations
* xbmc remote plugin
* transmission remote plugin
* xmpp service plugin


You Need (outdated!):
---------
* Wiring Pi Setup (https://github.com/WiringPi-Python)
* python
* python-pika (https://github.com/pika/pika)
* python-sqlite
* python-jabberbot (http://thp.io/2007/python-jabberbot/)
* python-psutil (http://code.google.com/p/psutil/)
* python-tz

MQueue Setup (also outdated!):
-------------
 apt-get  install rabbitmq-server
 rabbitmqctl add_user test test
 rabbitmqctl add_vhost test
 rabbitmqctl set_permissions -p test test ".*" ".*" ".*"



Technologies and software used (you guessed it: outdated!):
------------------
* XMPP http://en.wikipedia.org/wiki/Extensible_Messaging_and_Presence_Protocol
* AMQP http://en.wikipedia.org/wiki/AMQP
* Motion http://www.lavrsen.dk/foswiki/bin/view/Motion/WebHome
* eSpeak http://espeak.sourceforge.net/
* MPD http://mpd.wikia.com/wiki/Music_Player_Daemon_Wik
* Transmission http://www.transmissionbt.com/
* SQLite http://www.sqlite.org/
* XBMC Mediacenter http://wiki.xbmc.org/
* Raspberry Pi http://www.raspberrypi.org/
* Python Jabberbot http://thp.io/2007/python-jabberbot/


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


