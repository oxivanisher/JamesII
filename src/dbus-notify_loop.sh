#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
while true;
do
	clear
	./dbus-notify.py || sleep 20
	sleep 1

done
