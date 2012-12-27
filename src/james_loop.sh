#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
while true;
do
	clear
	echo "Doing git pull:"
	git pull
	sleep 1

	clear
	sudo ./james.py || pause
	sleep 1

done
