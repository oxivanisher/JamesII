#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR && git pull > /dev/null 2>&1
ls /var/run/screen > /dev/null 2>&1 || sudo /etc/init.d/screen-cleanup start > /dev/null 2>&1
$(which screen) -dmS JamesII $DIR/src/james_loop.sh
