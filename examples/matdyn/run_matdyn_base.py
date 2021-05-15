#!/usr/bin/env runaiida
from aiida import orm
from aiida.engine.launch import run_get_pk, submit
from aiida.orm.utils import load_node
from aiida.plugins.factories import DataFactory
from aiida_mobility.utils import (
    add_to_group,
    create_kpoints,
    print_help,
    read_structure,
    write_pk_to_file,
)
import argparse
from aiida_quantumespresso.workflows.matdyn.base import MatdynBaseWorkChain

# Please modify these according to your machine
str_matdyn = "qe-6.5-matdyn"


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA matdyn calculation."
    )
    parser.add_argument(
        "-S",
        "--structure",
        metavar="FILENAME",
        help="path to an input Structure(xsf,cif,poscar) file",
        required=True,
    )
    parser.add_argument(
        "--q2r",
        type=int,
        help="pk of q2r calculation",
    )
    parser.add_argument(
        "--asr",
        type=str,
        default="crystal",
        help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
    )
    parser.add_argument(
        "--distance",
        type=float,
        help="kpoint distance to get kpoints, default is 0.1",
        default=0.1,
    )
    parser.add_argument(
        "--system-2d",
        default=False,
        action="store_true",
        help="Set mesh to [x, x, 1]",
    )
    parser.add_argument(
        "-N", "--num_machines", type=int, help="number of machines", default=1
    )
    parser.add_argument(
        "-P",
        "--num_mpiprocs_per_machine",
        type=int,
        help="number of mpiprocs per machine",
        default=8,
    )
    parser.add_argument(
        "--walltime",
        type=int,
        help="the max wall time(hours) of calculation. default is 1 hours.",
        default=1,
    )
    parser.add_argument("-C", "--computer", type=str, default="qe")
    parser.add_argument(
        "-D",
        "--daemon",
        default=False,
        action="store_true",
        help="Run with submit",
    )
    parser.add_argument(
        "--group_name",
        type=str,
        help="Add this task to Group",
        default="matdyn_calculation",
    )
    return parser.parse_args()


def gen_kpoints(structure, distance, two_d=False):
    from aiida_quantumespresso.calculations.functions.seekpath_structure_analysis import (
        seekpath_structure_analysis,
    )
    from aiida_mobility.utils import constr2dpath

    inputs = {
        "reference_distance": distance,
        "metadata": {"call_link_label": "seekpath"},
    }
    result = seekpath_structure_analysis(structure, **inputs)

    kpath, kpathdict = constr2dpath(
        result["explicit_kpoints"].get_kpoints(),
        **result["explicit_kpoints"].attributes
    )
    kpoints = orm.KpointsData()
    kpoints.set_kpoints(kpath)
    kpoints.set_attribute("labels", kpathdict["labels"])
    kpoints.set_attribute("label_numbers", kpathdict["label_numbers"])

    return kpoints


def submit_workchain(
    structure_file,
    q2r,
    asr,
    distance,
    system_2d,
    num_machines,
    num_mpiprocs_per_machine,
    walltime,
    matdyn_code,
    daemon,
    group_name,
):

    try:
        last_calc = load_node(q2r)
        force_constants = last_calc.outputs.force_constants
    except Exception as e:
        print(e)
        raise SystemExit("Cannot get force_constants from Node {}.".format(q2r))

    structure = read_structure(structure_file)
    kpoints = gen_kpoints(structure, distance, two_d=system_2d)

    matdyn_calculation_parameters = {
        "matdyn": {
            "code": orm.Code.get_from_string(matdyn_code),
            "force_constants": force_constants,
            "parameters": orm.Dict(dict={"INPUT": {"asr": asr}}),
            "kpoints": kpoints,
            "metadata": {
                "options": {
                    "resources": {
                        "num_machines": num_machines,
                        "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                    },
                    "max_wallclock_seconds": 3600 * walltime,
                    "withmpi": True,
                }
            },
        }
    }
    if daemon is not None:
        workchain = submit(MatdynBaseWorkChain, **matdyn_calculation_parameters)
    else:
        workchain = run_get_pk(
            MatdynBaseWorkChain, **matdyn_calculation_parameters
        )

    add_to_group(workchain, group_name)
    print_help(workchain)
    write_pk_to_file(workchain, None, "matdyn")
    return workchain.pk


if __name__ == "__main__":
    args = parse_arugments()
    try:
        ["no", "simple", "crystal", "one-dim", "zero-dim"].index(args.asr)
    except ValueError as e:
        print(e)
        raise SystemExit("{} is not available.".format(args.asr))
    submit_workchain(
        args.structure,
        args.q2r,
        args.asr,
        args.distance,
        args.system_2d,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.walltime,
        "{}@{}".format(str_matdyn, args.computer),
        args.daemon,
        args.group_name,
    )
