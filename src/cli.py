#!/usr/bin/env python
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR
import sys
import james

core = james.Core(True)
core.load_plugin('cli')
core.run()
