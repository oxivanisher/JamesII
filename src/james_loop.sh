#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
GITPULL=true
while true;
do
	CRASH=false

	if $GITPULL;
	then
		clear
		echo -e "..:: Doing git pull ::..\n"
		git pull
	fi

	clear
	echo -e "..:: Starting james.py ($(date)) ::..\n"
	sudo ./james.py | sudo tee ./.james_crashed_log
	if [[ $? -eq 2 ]];
	then
		GITPULL=false
		echo -e "\nJamesII connection error detected. Sleeping for 20 seconds\n"
		sleep 20
	elif [[ $? -gt 0 ]];
	then
		GITPULL=true
		echo -e "\nJamesII crash detected. Sleeping for 20 seconds\n"
		echo $(date +%s) > ./.james_crashed
		chmod 666 ./.james_crashed
		sudo cat ./.james_crashed_log | mail root -s "JamesII Crash on $(hostname)"
		sleep 20
	else
		GITPULL=true
		echo -e "\nJamesII graceful shutdown detected\n"
		sleep 1
	fi
done
cd $INPWD