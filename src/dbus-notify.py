#!/usr/bin/env python

import sys
import james

core = james.Core(True)
core.load_plugin('system')
core.load_plugin('dbus-notify')
core.run()
