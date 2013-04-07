#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
$(which screen) -dmS JamesII $DIR/src/netlogger_loop.sh