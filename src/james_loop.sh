#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
while true;
do
	CRASH=false

	clear
	echo -e "..:: Doing git pull ::..\n"
	git pull

	clear
	echo -e "..:: Starting james.py ($(date)) ::..\n"
	sudo ./james.py
	if [[ $? -eq 2 ]];
		echo -e "\nJamesII connection error detected. Sleeping for 20 seconds\n"
		sleep 20
	elif [[ $? -gt 0 ]];
	then
		echo -e "\nJamesII crash detected. Sleeping for 20 seconds\n"
		echo $(date +%s) > ./.james_crashed
		chmod 666 ./.james_crashed
		sleep 20
	else
		echo -e "\nJamesII graceful shutdown detected\n"
		sleep 1
	fi
done
cd $INPWD