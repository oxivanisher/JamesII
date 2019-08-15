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

_term() {
  echo "Caught SIGTERM signal!"
  kill -TERM "$child" 2>/dev/null
  rm /var/lock/JamesII.pid
  cd $INPWD
}

trap _term SIGTERM

echo $$ > /var/lock/JamesII.pid

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR


echo -e "..:: Doing git pull ::..\n"
git pull
echo -e ""
fi

echo -e "..:: Starting james.py ($(date)) ::..\n"
sudo cp ./JamesII.log ./JamesII.log.old
sudo truncate -s0 ./JamesII.log
sudo chmod 666 ./JamesII.log
sudo script -q -c "./james.py" -e ./.james_console_log

child=$!
wait "$child"
