#!/bin/bash

while true;
do
	clear
	echo "Doing git pull:"
	git pull
	sleep 1

	clear
	sudo ./james.py || pause
	sleep 1

done
