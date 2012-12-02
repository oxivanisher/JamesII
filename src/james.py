#!/usr/bin/env python

import sys
import james

core = james.Core()
core.load_plugin('system')
core.load_plugin('espeak')
core.load_plugin('mpd')
core.load_plugin('raspberry')
core.load_plugin('sysstat')
core.run()