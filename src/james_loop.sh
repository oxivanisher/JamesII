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
	sudo ./james.py || sudo echo $(date +%s) > $HOME/.james_crashed && sleep 10
	sleep 1

done