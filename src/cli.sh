#!/bin/bash
INPWD=$(pwd)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

if [ -f "../venv/bin/python" ];
then
	pwd
	../venv/bin/python ./cli.py $@
else
	./cli.py $@
fi	

cd $INPWD >/dev/null 2>&1  
