#!/bin/bash

while true;
do
	clear
	sudo ./james.py || break
	sleep 1

	clear
	echo "Doing git pull:"
	git pull
	sleep 1
done
