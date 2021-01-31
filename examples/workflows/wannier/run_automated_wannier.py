#!/usr/bin/env runaiida
import argparse
import os
from aiida import orm
from aiida.engine import submit
from aiida.common.exceptions import NotExistent
from aiida_mobility.workflows.wannier.bands import Wannier90BandsWorkChain
from aiida_mobility.utils import (
    add_to_group,
    print_help,
    write_pk_to_file,
    read_structure,
)

# Please modify these according to your machine
str_pw = "qe-6.5-pw"
str_pw2wan = "pw2wannier90"
str_projwfc = "projwfc"
str_wan = "wannier-3.0"

group_name = "scdm_workflow"


def check_codes():
    # will raise NotExistent error
    try:
        codes = dict(
            pw_code=orm.Code.get_from_string(str_pw),
            pw2wannier90_code=orm.Code.get_from_string(str_pw2wan),
            projwfc_code=orm.Code.get_from_string(str_projwfc),
            wannier90_code=orm.Code.get_from_string(str_wan),
        )
    except NotExistent as e:
        print(e)
        print(
            "Please modify the code labels in this script according to your machine"
        )
        exit(1)
    return codes


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA workflows to automatically compute the MLWF using the SCDM method and the automated protocol described in the Vitale et al. paper"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    parser.add_argument(
        "-S",
        "--structure",
        metavar="FILENAME",
        help="path to an input Structure(xsf,cif,poscar) file",
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
    group.add_argument("--pseudos", help="pseudos json data of structures")
    group.add_argument("--pseudo-family", help="pseudo family name")
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
        "-m",
        "--do-mlwf",
        help="do maximal localization of Wannier functions",
        action="store_false",
    )
    parser.add_argument(
        "-d",
        "--do-disentanglement",
        help="do disentanglement in Wanner90 step (This should be False, otherwise band structure is not optimal!)",
        action="store_true",
    )
    parser.add_argument(
        "-v",
        "--only-valence",
        help="Compute only for valence bands (you must be careful to apply this only for insulators!)",
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--retrieve-hamiltonian",
        help="Retrieve Wannier Hamiltonian after the workflow finished",
        action="store_true",
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
        default=8,
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
        default="scdm_workflow",
    )
    args = parser.parse_args()
    if args.cutoffs is not None and args.pseudos is not None:
        print("[Warning]: cutoffs will replace the cutoffs in pseudos data.")
    return args


def update_group_name(
    group_name, only_valence, do_disen, do_mlwf, exclude_bands=None
):
    if only_valence:
        group_name += "_onlyvalence"
    else:
        group_name += "_withconduction"
    if do_disen:
        group_name += "_disentangle"
    if do_mlwf:
        group_name += "_mlwf"
    if exclude_bands is not None:
        group_name += "_excluded{}".format(len(exclude_bands))
    return group_name


def submit_workchain(
    structure_file,
    num_machines,
    num_mpiprocs_per_machine,
    protocol,
    parameters,
    pseudo_family,
    pseudos,
    only_valence,
    do_disentanglement,
    do_mlwf,
    retrieve_hamiltonian,
    run_relax,
    group_name,
    daemon,
    set_2d_mesh,
    cutoffs,
):
    codes = check_codes()

    group_name = update_group_name(
        group_name, only_valence, do_disentanglement, do_mlwf
    )

    if isinstance(structure_file, orm.StructureData):
        structure = structure_file
    else:
        structure = read_structure(structure_file)

    controls = {
        "retrieve_hamiltonian": orm.Bool(retrieve_hamiltonian),
        "only_valence": orm.Bool(only_valence),
        "do_disentanglement": orm.Bool(do_disentanglement),
        "do_mlwf": orm.Bool(do_mlwf),
    }

    if only_valence:
        print(
            "Running only_valence/insulating for {}".format(
                structure.get_formula()
            )
        )
    else:
        print(
            "Running with conduction bands for {}".format(
                structure.get_formula()
            )
        )

    modifiers = {"parameters": parameters}
    recommended_cutoffs = None
    if pseudos is not None:
        from aiida_quantumespresso.utils.protocols.pw import (
            _load_pseudo_metadata,
        )

        pseudo_json_data = _load_pseudo_metadata(pseudos)
        structure_name = os.path.splitext(structure_file)[0]
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

    wannier90_workchain_parameters = {
        "code": {
            "pw": codes["pw_code"],
            "pw2wannier90": codes["pw2wannier90_code"],
            "projwfc": codes["projwfc_code"],
            "wannier90": codes["wannier90_code"],
        },
        "protocol": orm.Dict(dict={"name": protocol, "modifiers": modifiers}),
        "structure": structure,
        "controls": controls,
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
        wannier90_workchain_parameters["pseudo_family"] = orm.Str(pseudo_family)
    if recommended_cutoffs is not None:
        wannier90_workchain_parameters["cutoffs"] = orm.Dict(
            dict=recommended_cutoffs
        )
    if run_relax:
        wannier90_workchain_parameters["should_run_relax"] = orm.Bool(run_relax)

    if daemon is not None:
        workchain = submit(
            Wannier90BandsWorkChain, **wannier90_workchain_parameters
        )
    else:
        from aiida.engine import run_get_pk
        from aiida.orm import load_node

        workchain = run_get_pk(
            Wannier90BandsWorkChain, **wannier90_workchain_parameters
        )

    add_to_group(workchain, group_name)
    print_help(workchain, structure)
    write_pk_to_file(workchain, structure, "wannier")

    return workchain.pk


if __name__ == "__main__":
    args = parse_arugments()
    str_pw += "@{}".format(args.computer)
    str_pw2wan += "@{}".format(args.computer)
    str_projwfc += "@{}".format(args.computer)
    str_wan += "@{}".format(args.computer)

    submit_workchain(
        args.structure,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        args.protocol,
        args.parameters,
        args.pseudo_family,
        args.pseudos,
        args.only_valence,
        args.do_disentanglement,
        args.do_mlwf,
        args.retrieve_hamiltonian,
        args.run_relax,
        args.group_name,
        args.daemon,
        args.set_2d_mesh,
        args.cutoffs,
    )
