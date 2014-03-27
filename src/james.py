#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import james

core = james.Core()
core.autoload_plugins()
core.run()