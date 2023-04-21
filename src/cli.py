#!/usr/bin/python3

import james

core = james.Core(True)
core.load_plugin('cli')
core.run()
