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

echo -e "..:: Doing git pull ::..\n"
git pull
echo -e ""

echo -e "..:: Starting james.py ($(date)) ::..\n"
if [ -f "../venv/bin/python" ];
then
	pwd
	sudo ../venv/bin/python ./james.py
else
	sudo ./james.py
fi	

case $? in
  0)
    echo -e "\nJamesII graceful shutdown detected\n"
    ;;
  2)
    echo -e "\nJamesII connection error detected. Sleeping for 10 seconds\n"
    ;;
  *)
    echo -e "\nJamesII crash detected. Sleeping for 10 seconds\n"
    echo $(date +%s) > ./.james_crashed
    chmod 666 ./.james_crashed
    echo -e "Console Log:\n$(tail -n 50 ./.james_console_log)\n\n\nJamesII Log:\n$(tail -n 100 ./JamesII.log) " | mail root -s "JamesII Crash on $(hostname)"
esac

rm /var/lock/JamesII.pid
