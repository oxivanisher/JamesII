#!/usr/bin/env python

import code
import readline
import atexit
import os
import sys
        
COMMANDS = ['extra', 'extension', 'stuff', 'errors',
            'email', 'foobar', 'foo']

def complete(text, state):
    for cmd in COMMANDS:
        if cmd.startswith(text):
            if not state:
                return cmd
            else:
                state -= 1

print os.name
print sys.platform

if sys.platform == 'darwin':
    readline.parse_and_bind ("bind ^I rl_complete")
else:
    readline.parse_and_bind("tab: complete")
    
readline.set_completer(complete)

histfile = "./.history" #os.path.join(os.path.expanduser("~"), ".pyhist")
try:
    readline.read_history_file(histfile)
except IOError:
    pass
import atexit
atexit.register(readline.write_history_file, histfile)

while True:
    line = raw_input()
    print line

del os, histfile