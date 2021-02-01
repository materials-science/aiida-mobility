#!/bin/bash
path=""
dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
for name in $(ls -d ${dir}/*/); do
    chmod +x -f ${name}*.py
    chmod +x -f ${name}*.sh
    path=$path:${name%%/} 
done
export PATH=$PATH$path