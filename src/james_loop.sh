#!/bin/bash

while true;
do
	clear
	./james.py || break
	sleep 1

	clear
	echo "Doing git pull:"
	git pull
	sleep 1
done
