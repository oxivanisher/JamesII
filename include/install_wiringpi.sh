#!/bin/bash

#debian:
sudo apt-get install python-dev build-essential python-setuptools
git clone git@github.com:WiringPi/WiringPi-Python.git
cd WiringPi-Python
git clone git@github.com:WiringPi/WiringPi.git
git submodule update --init
sudo python setup.py install
