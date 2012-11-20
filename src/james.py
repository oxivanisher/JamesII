#!/usr/bin/env python

import sys
import james

core = james.Core()
core.load_plugin('system')
core.load_plugin('espeak')
core.run()