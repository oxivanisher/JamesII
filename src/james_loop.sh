#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
while true;
do
	clear
	echo "..:: Doing git pull ::.."
	git pull

	clear
	echo "..:: Starting james.py ::.."
	sudo ./james.py || echo "JamesII quit detected with errorcode $?" && \
		echo $(date +%s) > /tmp/.james_crashed && \
		sudo mv /tmp/.james_crashed /root && \
		sleep 5
	sleep 1
done