<!--
 * @Author: your name
 * @Date: 2021-02-26 15:22:38
 * @LastEditTime: 2021-04-28 18:12:20
 * @LastEditors: Please set LastEditors
 * @Description: In User Settings Edit
 * @FilePath: /aiida-mobility/dev.md
-->

# Dev notes

## Schedules

- [ ] Automated relax

  - covergence criterion
    - [x] volume
    - [ ] total energy
  - protocol and parameters
    - `ms-1.0`

- [x] Automated ph

  - [x] deal with imaginary frequencies

- [ ] change `fildyn` to `xml` for perturbo support

## Issues

- [x] calculating ph at separated pointed will cause many redundant copies.
  - add `PARENT_FOLDER_SYMLINK`
- [ ] automatically set 2d mesh
- [ ] there is a bug in `seekpath_structure_analysis`, where `reference_distance` does not work.
      ![ #bugs ](https://img.shields.io/badge/seekpath-bugs-critical)
  - currently only found not work in `examples/run_matdyn_base.py`
- [ ] `flfrc` bug in `matdyn`
      ![ #matdyn #bugs ](https://img.shields.io/badge/matdyn-bugs-critical)

### ph

- [x] set `epsil` `True` or `False`
      Set `epsil` to `True` at the first point, and then switch off. Also, set `recover` to `False`.
- [x] after checking the first point, should start ph at every single point or just start from the second to the last?
      Plan to start at every point because of current failure from the second to the last.

  - :o: add `separated_points` flag

  - :x: [cannot reproduce] ~~Not only in the second to the last but failed in every attempt involved more than one point.~~

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
