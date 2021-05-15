#!/bin/bash
for file in $(ls *.xsf); do
    echo "Input Structure: ${file} ..."
    name=${file%%.*}
    mkdir ${name} -p
    cd ${name}
    for task in $(ls *.wannier); do
        wpk=${task%%.*}
    done
    cd '..'
    ./run_dft_bands.py -w ${wpk} -p 'accurate' -P 4 -C lz -D --pseudo-family 'sssp' --system-2d
    cd ${name}
    for task in $(ls *.dft); do
        dftpk=${task%%.*}
    done
    echo "Read dft bands task pk: ${dftpk} ..."
    cd '..'
done
