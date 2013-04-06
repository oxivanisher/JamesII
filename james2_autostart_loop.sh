#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
$(which screen) -dmS JamesII $DIR/src/james_loop.sh