#!/usr/bin/env python

import james

core = james.Core(True)
core.load_plugin('cli')
core.run()
