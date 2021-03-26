<!--
 * @Author: your name
 * @Date: 2021-02-26 15:22:38
 * @LastEditTime: 2021-03-06 17:15:34
 * @LastEditors: Please set LastEditors
 * @Description: In User Settings Edit
 * @FilePath: /aiida-mobility/dev.md
-->

# Dev notes

## Schedules

-   [ ] Automated relax

    -   covergence criterion
        -   [x] volume
        -   [ ] total energy
    -   parameters
        -   "kpoints_mesh_density": 0.2,
            -   make value of mesh around 20
            -   [ ] use large mesh to relax and then use smaller
        -   "convergence_threshold_per_atom": 1.0e-12
        -   "forc_conv_thr": 1.0e-8
        -   "etot_conv_thr": 1.0e-8
        -   "press_conv_thr": 1.0e-8
        -   "tstress": True
        -   "tprnfor": True
        -   "occupations": "fixed"
            -   only for ph calculation
        -   "nstep": 100
        -   "num_bands_factor": 2 # number of bands wrt number of occupied bands
        -   "assume_isolated": "2D"
        -   "cell_dofree": "2Dxy"
        -   "electron_maxstep": 200
        -   "diago_full_acc": True
        -   "mixing_mode": "local-TF"
        -   "mixing_beta": 0.7
        -   "vdw_corr": "DFT-D"
        -   "volume_convergence": 0.01

-   [ ] Automated ph
    -   [ ] deal with imaginary frequencies

## Issues

### ph

-   [ ] set `epsil` `True` or `False`
        Set `epsil` to `True` at the first point, and then switch off. Also, set `recover` to `False`.
-   [ ] after checking the first point, should start ph at every single point or just start from the second to the last?
        Plan to start at every point because of current failure from the second to the last.

        Not only in the second to the last but failed in every attempt involved more than one point.

    ```bash
    *** Error in `/home/lz/soft/qe-6.5/bin/ph.x': corrupted size vs. prev_size: 0x0000000007848a90 ***
    ======= Backtrace: =========
    /lib64/libc.so.6(+0x80da7)[0x7f98063ceda7]
    /lib64/libc.so.6(+0x82275)[0x7f98063d0275]
    /lib64/libc.so.6(__libc_malloc+0x4c)[0x7f98063d384c]
    /opt/intel/compilers_and_libraries_2018.1.163/linux/mpi/intel64/lib/libmpi.so.12(+0x41ce23)[0x7f9807461e23]
    /opt/intel/compilers_and_libraries_2018.1.163/linux/mpi/intel64/lib/libmpi.so.12(+0xfd186)[0x7f9807142186]
    /opt/intel/compilers_and_libraries_2018.1.163/linux/mpi/intel64/lib/libmpi.so.12(MPI_Alltoall+0xc2f)[0x7f9807144b4f]
    /opt/intel/compilers_and_libraries_2018.1.163/linux/mpi/intel64/lib/libmpifort.so.12(mpi_alltoall__+0x7e)[0x7f9807d2142e]
    /home/lz/soft/qe-6.5/bin/ph.x[0xba0dd6]
    /home/lz/soft/qe-6.5/bin/ph.x[0xb9f5e0]
    /home/lz/soft/qe-6.5/bin/ph.x[0xbab9ca]
    /home/lz/soft/qe-6.5/bin/ph.x[0xba818f]
    /home/lz/soft/qe-6.5/bin/ph.x[0x5a3898]
    /home/lz/soft/qe-6.5/bin/ph.x[0x524366]
    /home/lz/soft/qe-6.5/bin/ph.x[0x48e457]
    /home/lz/soft/qe-6.5/bin/ph.x[0x4628b4]
    /home/lz/soft/qe-6.5/bin/ph.x[0x40d571]
    /home/lz/soft/qe-6.5/bin/ph.x[0x406ade]
    /home/lz/soft/qe-6.5/bin/ph.x[0x406a1e]
    /lib64/libc.so.6(__libc_start_main+0xf5)[0x7f9806370445]
    /home/lz/soft/qe-6.5/bin/ph.x[0x406929]
    ======= Memory map: ========
    00400000-011b4000 r-xp 00000000 08:10 28058837                           /home/lz/soft/qe-6.5/PHonon/PH/ph.x
    013b4000-013b7000 r--p 00db4000 08:10 28058837                           /home/lz/soft/qe-6.5/PHonon/PH/ph.x
    013b7000-01612000 rw-p 00db7000 08:10 28058837                           /home/lz/soft/qe-6.5/PHonon/PH/ph.x
    01612000-035d0000 rw-p 00000000 00:00 0
    047fa000-0974e000 rw-p 00000000 00:00 0                                  [heap]
    7f97e0000000-7f97e0021000 rw-p 00000000 00:00 0
    7f97e0021000-7f97e4000000 ---p 00000000 00:00 0
    7f97e6967000-7f97e6d7a000 rw-p 00000000 00:00 0
    7f97e6d7a000-7f97eaa42000 r-xp 00000000 00:2b 10358239                   /opt/intel/compilers_and_libraries_2018.1.163/linux/mkl/lib/intel64_lin/libmkl_avx512.so
    7f97eaa4
    ```
