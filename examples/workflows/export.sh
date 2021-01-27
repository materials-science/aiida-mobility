#!/bin/bash
for file in $(ls *.xsf); do
    echo "Input Structure: ${file} ..."
    name=${file%%.*}
    cd ${name}
    for task in $(ls *.wannier); do
        wpk=${task%%.*}
    done
    echo "Read wannier task pk: ${wpk} ..."

    for task in $(ls *.dft); do
        dftpk=${task%%.*}
    done
    echo "Read dft bands task pk: ${dftpk} ..."

    # export
    ../export_bands.py -W ${wpk} -B ${dftpk} -P
    cd '..'
done
