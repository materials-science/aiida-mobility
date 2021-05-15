#!/bin/bash
for file in $(ls *.xsf); do
    echo "Input Structure: ${file} ..."
    name=${file%%.*}
    mkdir ${name} -p
    ./run_automated_wannier.py -S ${file} -p 'accurate' -P 16 -C lz -D --pseudo-family 'sssp' --system_2d
    cd ${name}
    for task in $(ls *.wannier); do
        wpk=${task%%.*}
    done
    echo "Read wannier task pk: ${wpk} ..."
    cd '..'
done
