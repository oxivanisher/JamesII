#!/usr/bin/env python

import sys
import james

core = james.Core()
core.autoload_plugins()
core.run()