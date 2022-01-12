#!/usr/bin/env runaiida
import argparse
from aiida_mobility.utils import (
    add_to_group,
    create_kpoints,
    print_help,
    read_structure,
    write_pk_to_file,
)
from aiida import orm
from aiida_mobility.workflows.ph.base import PhBaseWorkChain
from aiida.engine import submit, run_get_pk
from aiida.orm import load_node


# Please modify these according to your machine
str_ph = "qe-6.5-ph"


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA workflows to automatically compute the MLWF using the SCDM method and the automated protocol described in the Vitale et al. paper"
    )
    parser.add_argument(
        "-S",
        "--structure",
        metavar="FILENAME",
        help="path to an input Structure(xsf,cif,poscar) file",
        required=True,
    )
    parser.add_argument(
        "--node",
        type=int,
        help="pk of scf calculation or pk of last ph node",
    )
    parser.add_argument(
        "--node_mode",
        default=False,
        help="whether the mode of parent calculation is scf.",
        action="store_true",
    )
    parser.add_argument(
        "--tr2_ph",
        type=float,
        help="tr2_ph, default is 1.0e-15",
        default=1.0e-15,
    )
    parser.add_argument(
        "--qpoints",
        nargs=3,
        type=int,
        help="The number of points in the qpoint mesh along each basis vector.",
    )
    parser.add_argument(
        "--epsil",
        help="epsil, default is False",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--distance",
        type=float,
        help="qpoint distance to get qpoints, default is 0.1",
        default=0.1,
    )
    parser.add_argument(
        "--system-2d",
        default=False,
        action="store_true",
        help="Set mesh to [x, x, 1]",
    )
    parser.add_argument(
        "--start_test",
        default=False,
        action="store_true",
        help="Only calculate the first point. The separated_qpoints will be True",
    )
    parser.add_argument(
        "--check_imaginary_frequencies",
        default=False,
        help="Whether to check imaginary frequencies.",
        action="store_true",
    )
    parser.add_argument(
        "--frequency_threshold",
        type=float,
        help="imaginary_frequency_threshold, default is -20",
        default=-20,
    )
    parser.add_argument(
        "--separated_qpoints",
        default=False,
        action="store_true",
        help="Set true if you want to calculate each qpoint separately.",
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
        help="the max wall time(hours) of calculation. default is 24 hours.",
        default=24,
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
        default="ph_workflow",
    )

    return parser.parse_args()


def submit_workchain(
    structure_file,
    node,
    node_mode,
    qpoints,
    tr2_ph,
    epsil,
    distance,
    system_2d,
    start_test,
    check_imaginary_frequencies,
    frequency_threshold,
    separated_qpoints,
    num_machines,
    num_mpiprocs_per_machine,
    walltime,
    ph_code,
    daemon,
    group_name,
):
    last_calc = load_node(node)
    try:
        parent_folder = (
            last_calc.get_outgoing(
                node_class=orm.RemoteData, link_label_filter="remote_folder"
            )
            .one()
            .node
        )
    except Exception as e:
        print(e)
        raise SystemError("Cannot get remote folder from Node {}.".format(node))

    structure = read_structure(structure_file)
    if qpoints is not None:
        try:
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(qpoints)
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {qpoints}\n{exception}"
            )
    else:
        kpoints = create_kpoints(structure, distance, system_2d)

    inputph_parameters = {
        "INPUTPH": {
            "tr2_ph": tr2_ph,
            "epsil": epsil,
            "lqdir": True,
            "fildvscf": "dvscf",
        }
    }

    if start_test:
        inputph_parameters["INPUTPH"]["start_q"] = 1
        inputph_parameters["INPUTPH"]["last_q"] = 1
        separated_qpoints = True

    ph_calculation_parameters = {
        "ph": {
            "code": orm.Code.get_from_string(ph_code),
            "qpoints": kpoints,
            "parameters": orm.Dict(dict=inputph_parameters),
            "parent_folder": parent_folder,
            "metadata": {
                "options": {
                    "resources": {
                        "num_machines": num_machines,
                        "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                    },
                    "max_wallclock_seconds": 3600 * walltime,
                    "withmpi": True,
                },
            },
        },
        "check_imaginary_frequencies": orm.Bool(check_imaginary_frequencies),
        "separated_qpoints": orm.Bool(separated_qpoints),
        "frequency_threshold": orm.Float(frequency_threshold),
        "parent_scf_node_mode": orm.Bool(node_mode),
    }

    if daemon is not None:
        workchain = submit(PhBaseWorkChain, **ph_calculation_parameters)
    else:
        workchain = run_get_pk(PhBaseWorkChain, **ph_calculation_parameters)

    add_to_group(workchain, group_name)
    print_help(workchain, structure)
    write_pk_to_file(workchain, structure, "ph")
    return workchain.pk


if __name__ == "__main__":
    args = parse_arugments()
    submit_workchain(
        args.structure,
        args.node,
        args.node_mode,
        args.qpoints,
        args.tr2_ph,
        args.epsil,
        args.distance,
        args.system_2d,
        args.start_test,
        args.check_imaginary_frequencies,
        args.frequency_threshold,
        args.separated_qpoints,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.walltime,
        "{}@{}".format(str_ph, args.computer),
        args.daemon,
        args.group_name,
    )
