#!/bin/bash
INPWD=$(pwd)

if [[ -f "/var/lock/JamesII.pid" ]];
then
	PID=$(cat /var/lock/JamesII.pid)
	if kill -0 $PID > /dev/null 2>&1;
	then
		exit
	fi
fi

echo $$ > /var/lock/JamesII.pid

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
GITPULL=true
while true;
do
	CRASH=false

	if $GITPULL;
	then
		echo -e "..:: Doing git pull ::..\n"
		git pull
		echo -e ""
	fi

	echo -e "..:: Starting james.py ($(date)) ::..\n"
	
	# Log cleanup to not fill the disks
	if [[ -f .james_console_log ]];
	then
		echo -e "Truncating .james_console_log\n"
		sudo truncate -s0 ./.james_console_log
	fi
	
	if [[ -f ./JamesII.log.old ]];
	then
		echo -e "\nRemoving old ./JamesII.log.old"
		sudo rm ./JamesII.log.old
	fi
	
	sudo truncate -s0 ./JamesII.log
	sudo chmod 666 ./JamesII.log
	sudo script -q -c "./james.py" -e ./.james_console_log ; RESULT=${PIPESTATUS[0]}
	if [[ $RESULT -eq 0 ]];
	then
		GITPULL=true
		echo -e "\nJamesII graceful shutdown detected\n"
		sleep 3
	elif [[ $RESULT -eq 2 ]];
	then
		GITPULL=false
		echo -e "\nJamesII connection error detected. Sleeping for 10 seconds\n"
		sleep 10
	elif [[ $RESULT -eq 3 ]];
	then
		GITPULL=true
		echo -e "\nJamesII keyboard interrupt detected. Sleeping for 10 seconds\n"
		sleep 10
	else
		GITPULL=true
		echo -e "\nJamesII crash detected. Sleeping for 10 seconds\n"
		echo $(date +%s) > ./.james_crashed
		chmod 666 ./.james_crashed
		echo -e "Console Log:\n$(sudo tail -n 100 ./.james_console_log)\n\n\nJamesII Log:\n$(sudo cat ./JamesII.log) " | mail root -s "JamesII Crash on $(hostname)"
		sleep 10
	fi
done
rm /var/lock/JamesII.pid
cd $INPWD
