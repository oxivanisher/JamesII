#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
sudo /etc/init.d/screen-cleanup start > /dev/null 2>&1
$(which screen) -dmS JamesII $DIR/src/james_loop.sh