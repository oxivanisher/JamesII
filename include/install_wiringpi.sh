#!/bin/bash

#debian:
sudo apt-get install -y python-dev build-essential python-setuptools
git clone https://github.com/WiringPi/WiringPi-Python.git
cd WiringPi-Python
git clone git://git.drogon.net/wiringPi
git submodule update --init
cd WiringPi
./build
cd ..
sudo python setup.py install
