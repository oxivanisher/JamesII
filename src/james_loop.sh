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
	sudo mv ./JamesII.log ./JamesII.log.old 2>&1 >/dev/null
	sudo touch ./JamesII.log
	sudo chmod 666 ./JamesII.log
	sudo script -c "./james.py" -e ./.james_console_log ; RESULT=${PIPESTATUS[0]}
	if [[ $RESULT -eq 0 ]];
	then
		GITPULL=true
		echo -e "\nJamesII graceful shutdown detected\n"
		sleep 1
	elif [[ $RESULT -eq 2 ]];
	then
		GITPULL=false
		echo -e "\nJamesII connection error detected. Sleeping for 20 seconds\n"
		sleep 20
	elif [[ $RESULT -eq 3 ]];
	then
		GITPULL=true
		echo -e "\nJamesII keyboard interrupt detected. Sleeping for 20 seconds\n"
		sleep 20
	else
		GITPULL=true
		echo -e "\nJamesII crash detected. Sleeping for 20 seconds\n"
		echo $(date +%s) > ./.james_crashed
		chmod 666 ./.james_crashed
		echo -e "Console Log:\n$(sudo cat ./.james_console_log)\n\n\nJamesII Log:\n$(sudo cat ./JamesII.log) " | mail root -s "JamesII Crash on $(hostname)"
		sleep 20
	fi
done
cd $INPWD