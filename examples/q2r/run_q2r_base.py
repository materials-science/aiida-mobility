#!/usr/bin/env runaiida
from aiida import orm
from aiida.engine.launch import run_get_pk, submit
from aiida.orm.utils import load_node
from aiida_mobility.utils import add_to_group, print_help, write_pk_to_file
import argparse
from aiida_quantumespresso.workflows.q2r.base import Q2rBaseWorkChain

# Please modify these according to your machine
str_q2r = "qe-6.5-q2r"


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA q2r calculation."
    )
    parser.add_argument(
        "--ph",
        type=int,
        help="pk of ph calculation",
    )
    parser.add_argument(
        "--zasr",
        type=str,
        default="crystal",
        help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
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
        default="q2r_calculation",
    )
    return parser.parse_args()


def submit_workchain(
    ph,
    num_machines,
    num_mpiprocs_per_machine,
    walltime,
    q2r_code,
    zasr,
    daemon,
    group_name,
):
    last_calc = load_node(ph)
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
        raise SystemError("Cannot get remote folder from Node {}.".format(ph))
    q2r_calculation_parameters = {
        "q2r": {
            "code": orm.Code.get_from_string(q2r_code),
            "parent_folder": parent_folder,
            "parameters": orm.Dict(dict={"INPUT": {"zasr": zasr}}),
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
        workchain = submit(Q2rBaseWorkChain, **q2r_calculation_parameters)
    else:
        workchain = run_get_pk(Q2rBaseWorkChain, **q2r_calculation_parameters)

    add_to_group(workchain, group_name)
    print_help(workchain)
    write_pk_to_file(workchain, None, "q2r")
    return workchain.pk


if __name__ == "__main__":
    args = parse_arugments()
    try:
        ["no", "simple", "crystal", "one-dim", "zero-dim"].index(args.zasr)
    except ValueError as e:
        print(e)
        raise SystemExit("{} is not available.".format(args.zasr))

    submit_workchain(
        args.ph,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.walltime,
        "{}@{}".format(str_q2r, args.computer),
        args.zasr,
        args.daemon,
        args.group_name,
    )
