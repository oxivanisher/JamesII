#!/bin/bash

while true;
do
	clear
	sudo ./dbus-notify.py || sleep 30
	sleep 1

done
