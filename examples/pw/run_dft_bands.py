#!/usr/bin/env runaiida
import os
from aiida_mobility.utils import (
    add_to_group,
    write_pk_to_file,
    print_help,
    read_structure,
)
import argparse
from aiida import orm
from aiida.engine import submit, run_get_node
from aiida_mobility.workflows.pw.band_structure import (
    PwBandStructureWorkChain,
)
from aiida_mobility.workflows.wannier.bands import Wannier90BandsWorkChain

# Please modify these according to your machine
code_str = "qe-6.5-pw"
code = None


def parse_argugments():
    parser = argparse.ArgumentParser(
        "A script to run the DFT band structure (without structural relax) using Quantum ESPRESSO starting from an automated workflow (to reuse structure), or from XSF file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-x", "--xsf", help="path to an input XSF file")
    group.add_argument(
        "-w",
        "--workchain",
        help="The PK of the Wannier90BandsWorkChain - if you didn't run it, run it first using the ./run_automated_wannier.py script",
    )
    parser.add_argument(
        "-p",
        "--parameters",
        help="available parameters protocols are 'fast', 'default' and 'accurate'",
        default="default",
    )
    parser.add_argument(
        "--protocol",
        help="available protocols are 'theos-ht-1.0' and 'testing'",
        default="theos-ht-1.0",
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
        "--set_2d_mesh",
        default=False,
        action="store_true",
        help="Set mesh to [x, x, 1]",
    )
    parser.add_argument(
        "--run-relax",
        default=False,
        help="Whether to run relax before scf.",
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
        default="ph_base_workflow",
    )
    args = parser.parse_args()
    if args.xsf is not None:
        structure = read_structure(args.xsf)
    else:
        wannier90_workchain_pk = int(args.workchain)
        try:
            wannier90_workchain = orm.load_node(wannier90_workchain_pk)
        except Exception:
            print(
                "I could not load an AiiDA node with PK={}, did you use the correct PK?".format(
                    wannier90_workchain
                )
            )
            exit()
        if wannier90_workchain.process_class != Wannier90BandsWorkChain:
            print(
                "The node with PK={} is not a Wannier90BandsWorkChain, it is a {}".format(
                    wannier90_workchain_pk, type(wannier90_workchain)
                )
            )
            print(
                "Please pass a node that was the output of the Wannier90 workflow executed using"
            )
            print("the ./run_automated_wannier.py script.")
            exit()
        structure = wannier90_workchain.inputs.structure
    return structure, args


def submit_workchain(
    structure,
    daemon,
    protocol,
    parameters,
    pseudo_family,
    pseudos,
    run_relax,
    num_machines,
    num_mpiprocs_per_machine,
    set_2d_mesh,
    cutoffs,
    kpoints_mesh,
):
    print(
        "running dft band structure calculation for {}".format(
            structure.get_formula()
        )
    )

    # Set custom pseudo
    modifiers = {"parameters": parameters}
    recommended_cutoffs = None
    if pseudos is not None:
        from aiida_quantumespresso.utils.protocols.pw import (
            _load_pseudo_metadata,
        )

        pseudo_json_data = _load_pseudo_metadata(pseudos)
        structure_name = structure.get_formula()
        if structure_name in pseudo_json_data:
            pseudo_dict = pseudo_json_data[structure_name]
            if "pseudo_family" in pseudo_dict:
                pseudo_family = pseudo_dict["pseudo_family"]
                recommended_cutoffs = {
                    "cutoff": pseudo_dict["cutoff"],
                    "dual": pseudo_dict["dual"],
                }
            elif "pseudos" in pseudo_dict:
                pseudo_data = {}
                pseudo_map = pseudo_dict["pseudos"]
                for ele in pseudo_map:
                    pseudo_data[ele] = pseudo_map[ele]
                    pseudo_data[ele].update(
                        {
                            "cutoff": pseudo_dict["cutoff"],
                            "dual": pseudo_dict["dual"],
                        }
                    )
                modifiers.update(
                    {"pseudo": "custom", "pseudo_data": pseudo_data}
                )
            else:
                print(
                    "neither pseudo_family or pseudos is provided in json data"
                )
                exit(1)
        else:
            print(
                "No structure found in json data. Please check your filename."
            )
            exit(1)

    if cutoffs is not None and len(cutoffs) == 2:
        recommended_cutoffs = {"cutoff": cutoffs[0], "dual": cutoffs[1]}

    # Submit the DFT bands workchain
    pwbands_workchain_parameters = {
        "code": code,
        "structure": structure,
        "protocol": orm.Dict(dict={"name": protocol, "modifiers": modifiers}),
        "options": orm.Dict(
            dict={
                "resources": {
                    "num_machines": num_machines,
                    "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                },
                "max_wallclock_seconds": 3600 * 5,
                "withmpi": True,
            }
        ),
        "set_2d_mesh": orm.Bool(set_2d_mesh),
    }
    if pseudo_family is not None:
        pwbands_workchain_parameters["pseudo_family"] = orm.Str(pseudo_family)

    if kpoints_mesh is not None:
        try:
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(kpoints_mesh)
            pwbands_workchain_parameters["kpoints"] = kpoints
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {args.kpoints_mesh}\n{exception}"
            )

    if recommended_cutoffs is not None:
        pwbands_workchain_parameters["cutoffs"] = orm.Dict(
            dict=recommended_cutoffs
        )

    if run_relax:
        pwbands_workchain_parameters["should_run_relax"] = orm.Bool(run_relax)

    if daemon:
        dft_workchain = submit(
            PwBandStructureWorkChain, **pwbands_workchain_parameters
        )
    else:
        from aiida.engine import run_get_pk

        dft_workchain = run_get_pk(
            PwBandStructureWorkChain, **pwbands_workchain_parameters
        )
    return dft_workchain


if __name__ == "__main__":
    structure, args = parse_argugments()
    code_str += "@{}".format(args.computer)
    code = orm.Code.get_from_string(code_str)
    workchain = submit_workchain(
        structure,
        args.daemon,
        args.protocol,
        args.parameters,
        args.pseudo_family,
        args.pseudos,
        args.run_relax,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.set_2d_mesh,
        args.cutoffs,
        args.kpoints_mesh,
    )

    add_to_group(workchain, args.group_name)
    print_help(workchain, structure)
    write_pk_to_file(workchain, structure, "dft")
