#!/bin/bash

#debian:
sudo apt-get install -y python-dev build-essential python-setuptools
# git clone https://github.com/WiringPi/WiringPi-Python.git
git clone https://github.com/WiringPi/WiringPi2-Python.git
# cd WiringPi-Python
sudo pip install wiringpi2

# cd WiringPi2-Python
git clone git://git.drogon.net/wiringPi
# git submodule update --init
# cd WiringPi
cd wiringPi
./build
cd ..
sudo python setup.py install
