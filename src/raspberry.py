#!/usr/bin/env python

import sys
import james

core = james.Core()
core.load_plugin('raspberry')
core.run()