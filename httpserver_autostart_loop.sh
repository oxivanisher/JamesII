#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
$(which screen) -dmS HTTPServer_JamesII $DIR/src/httpserver_loop.sh