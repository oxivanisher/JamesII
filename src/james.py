#!/usr/bin/env python

import sys
import james

core = james.Core()
#core.execute_command(sys.argv[1:])

core.input_channel.write(" ".join(sys.argv[1:]))
