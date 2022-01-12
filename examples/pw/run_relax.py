#!/usr/bin/env runaiida
from aiida_mobility.utils import (
    add_to_group,
    get_protocol,
    get_pw_common_inputs,
    write_pk_to_file,
    print_help,
    read_structure,
)
import argparse
from aiida import orm
from aiida.engine import submit, run_get_node
from aiida_mobility.workflows.pw.relax import PwRelaxWorkChain

# Please modify these according to your machine
code_str = "qe-6.5-pw"


def parse_argugments():
    parser = argparse.ArgumentParser(
        "A script to run the structural relax using Quantum ESPRESSO starting from the Workchain or a structure file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-x", "--xsf", help="path to an input XSF file")
    group.add_argument(
        "-w",
        "--workchain",
        help="The PK of the PwRelaxWorkChain",
    )
    parser.add_argument(
        "-p",
        "--parameters",
        help="available parameters protocols are 'fast', 'default' and 'accurate'",
        default="default",
    )
    parser.add_argument(
        "--protocol",
        help="available protocols are 'theos-ht-1.0', 'ms-1.0' and 'testing'",
        default="ms-1.0",
    )
    pseudos_group = parser.add_mutually_exclusive_group(required=True)
    pseudos_group.add_argument(
        "--pseudos", help="pseudos json data of structures"
    )
    pseudos_group.add_argument("--pseudo-family", help="pseudo family name")
    parser.add_argument(
        "--kpoints-mesh",
        nargs=3,
        type=int,
        help="The number of points in the kpoint mesh along each basis vector.",
    )
    parser.add_argument(
        "--cutoffs",
        type=float,
        nargs=2,
        default=None,
        help="should be [ecutwfc] [dual]. [ecutrho] will get by dual * ecutwfc",
    )
    parser.add_argument(
        "--system-2d",
        default=False,
        action="store_true",
        help="Set mesh to [x, x, 1]",
    )
    parser.add_argument(
        "--vc-relax",
        default=False,
        help="Whether to run vc-relax before scf.",
        action="store_true",
    )
    parser.add_argument(
        "-N", "--num_machines", type=int, help="number of machines", default=1
    )
    parser.add_argument(
        "-P",
        "--num_mpiprocs_per_machine",
        type=int,
        help="number of mpiprocs per machine",
        default=4,
    )
    parser.add_argument("-C", "--computer", type=str, default="qe")
    parser.add_argument("-D", "--daemon", default=False, action="store_true")
    parser.add_argument(
        "--group_name",
        type=str,
        help="Add this task to Group",
        default="pw_relax_workflow",
    )
    args = parser.parse_args()
    if args.xsf is not None:
        structure = read_structure(args.xsf)
    else:
        relax_workchain_pk = int(args.workchain)
        try:
            relax_workchain = orm.load_node(relax_workchain_pk)
        except Exception:
            print(
                "I could not load an AiiDA node with PK={}, did you use the correct PK?".format(
                    relax_workchain
                )
            )
            exit()
        if relax_workchain.process_class != PwRelaxWorkChain:
            print(
                "The node with PK={} is not a PwRelaxWorkChain, it is a {}".format(
                    relax_workchain_pk, type(relax_workchain)
                )
            )
            print(
                "Please pass a node that was the output of the PWRelax workflow executed using"
            )
            exit()
        structure = relax_workchain.outputs.output_structure
    return structure, args


def submit_workchain(
    structure,
    daemon,
    protocol,
    parameters,
    pseudo_family,
    pseudos,
    num_machines,
    num_mpiprocs_per_machine,
    system_2d,
    vc_relax,
    kpoints_mesh,
    cutoffs=None,
):
    print(
        "running relax structure calculation for {}".format(
            structure.get_formula()
        )
    )

    protocol, recommended_cutoffs = get_protocol(
        structure, parameters, protocol, pseudos
    )

    # Submit the Relax workchain
    relax_mode = "vc-relax" if vc_relax else "relax"
    relax_workchain_parameters = {
        "structure": structure,
        "base": get_pw_common_inputs(
            structure,
            code_str,
            protocol,
            recommended_cutoffs,
            pseudo_family,
            cutoffs,
            system_2d,
            num_machines,
            num_mpiprocs_per_machine,
            mode=relax_mode,
        ),
        "relaxation_scheme": orm.Str(relax_mode),
        "meta_convergence": orm.Bool(protocol["meta_convergence"]),
        # "max_meta_convergence_iterations": orm.Int(10),
        "volume_convergence": orm.Float(protocol["volume_convergence"]),
        # "system_2d": orm.Bool(system_2d),
    }
    parameters = relax_workchain_parameters["base"]["pw"][
        "parameters"
    ].get_dict()
    parameters.setdefault(
        "CELL", {"press_conv_thr": protocol["press_conv_thr"]}
    )
    relax_workchain_parameters["base"]["pw"]["parameters"] = orm.Dict(
        dict=parameters
    )

    if kpoints_mesh is not None:
        try:
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(kpoints_mesh)
            relax_workchain_parameters["base"]["kpoints"] = kpoints
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {args.kpoints_mesh}\n{exception}"
            )

    if daemon:
        relax_workchain = submit(PwRelaxWorkChain, **relax_workchain_parameters)
    else:
        from aiida.engine import run_get_pk

        relax_workchain = run_get_pk(
            PwRelaxWorkChain, **relax_workchain_parameters
        )
    return relax_workchain


if __name__ == "__main__":
    structure, args = parse_argugments()
    code_str += "@{}".format(args.computer)
    workchain = submit_workchain(
        structure,
        args.daemon,
        args.protocol,
        args.parameters,
        args.pseudo_family,
        args.pseudos,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.system_2d,
        args.vc_relax,
        args.kpoints_mesh,
        args.cutoffs,
    )

    add_to_group(workchain, args.group_name)
    print_help(workchain, structure)
    write_pk_to_file(workchain, structure, "relax")
