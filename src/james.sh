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
	sudo "../venv/bin/python ./james.py"
else
	sudo "./james.py"
fi	
rm /var/lock/JamesII.pid
