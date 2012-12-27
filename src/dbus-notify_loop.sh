#!/bin/bash

while true;
do
	clear
	./dbus-notify.py || sleep 30
	sleep 1

done
