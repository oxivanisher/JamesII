#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
$(which screen) -dmS NetLogger_JamesII $DIR/src/netlogger_loop.sh