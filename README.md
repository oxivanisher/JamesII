James II: Your Butler
=====================

James your Butler brought to the next level.

The Idea behing James Butler is to implement smarthome functions and ideas to your existing infrastraucture like:
* Linux Computers
* Raspberry Pi
* XBMC Mediacenter
* Transmission
* Motion


You Need:
---------
* python
* python-carrot (http://packages.python.org/carrot/)


Technologies and software used:
------------------
* XMPP (http://en.wikipedia.org/wiki/Extensible_Messaging_and_Presence_Protocol)
* AMQP (http://en.wikipedia.org/wiki/AMQP)
* Motion (http://www.lavrsen.dk/foswiki/bin/view/Motion/WebHome)
* [http://espeak.sourceforge.net/ eSpeak]
* MPD [http://mpd.wikia.com/wiki/Music_Player_Daemon_Wik]
* Transmission (http://www.transmissionbt.com/)


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


