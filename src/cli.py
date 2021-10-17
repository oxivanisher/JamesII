#!/usr/bin/python2

import sys
import james

core = james.Core(True)
core.load_plugin('cli')
core.run()
