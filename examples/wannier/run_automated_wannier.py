#!/usr/bin/env runaiida
import argparse
import os
from aiida import orm
from aiida.engine import submit
from aiida.common.exceptions import NotExistent
from aiida_mobility.workflows.wannier.bands import Wannier90BandsWorkChain
from aiida_mobility.utils import (
    StoreDictKeyPair,
    add_to_group,
    print_help,
    write_pk_to_file,
    read_structure,
)

# Please modify these according to your machine
str_pw = "qe-6.5-pw"
str_pw2wan = "pw2wannier90"
str_projwfc = "projwfc"
str_wan = "wannier-3.1"
str_opengrid = "qe-git-opengrid@localhost"

group_name = "scdm_workflow"


def check_codes():
    # will raise NotExistent error
    try:
        codes = dict(
            pw=orm.Code.get_from_string(str_pw),
            pw2wannier90=orm.Code.get_from_string(str_pw2wan),
            projwfc=orm.Code.get_from_string(str_projwfc),
            wannier90=orm.Code.get_from_string(str_wan),
        )
    except NotExistent as e:
        print(e)
        print(
            "Please modify the code labels in this script according to your machine"
        )
        exit(1)
    # optional code
    try:
        codes["opengrid"] = orm.Code.get_from_string(str_opengrid)
    except NotExistent:
        pass
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
        "--protocol",
        help="available protocols are 'theos-ht-1.0' and 'ms-1.0'",
        default="ms-1.0",
    )
    parser.add_argument(
        "--parameters-set",
        help="available scf parameters sets of protocols are {`fast`, `default` and `accurate`}_{``, `gaussian`}",
        default="default",
    )
    parser.add_argument(
        "-p",
        "--parameters",
        nargs="+",
        action=StoreDictKeyPair,
        default=None,
        help="Override parameters in protocol by specifying the key and value of parameter. e.g. <ecutwfc=80>...",
        metavar="KEY1=VAL1 KEY2=VAL2...",
    )
    group.add_argument("--pseudos", help="pseudos json data of structures")
    group.add_argument("--pseudo-family", help="pseudo family name")
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
        "--use-primitive-structure",
        default=False,
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
        "--plot-wannier-functions",
        help="Group name that the calculations will be added to.",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--do-disentanglement",
        help="do disentanglement in Wanner90 step (This should be False, otherwise band structure is not optimal!)",
        action="store_true",
    )
    parser.add_argument(
        "-m",
        "--do-mlwf",
        help="do maximal localization of Wannier functions",
        action="store_false",
    )
    parser.add_argument(
        "--write-u-matrices",
        help="Group name that the calculations will be added to.",
        action="store_true",
    )
    parser.add_argument(
        "--soc",
        default=False,
        help="spin_orbit_coupling",
        action="store_true",
    )
    parser.add_argument(
        "--run-dft",
        default=False,
        help="Whether to run compare_dft_bands.",
        action="store_true",
    )
    # parser.add_argument(
    #     "--run-relax",
    #     default=False,
    #     help="Whether to run relax before scf.",
    #     action="store_true",
    # )
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
        "--group-name",
        type=str,
        help="Add this task to Group",
        default="scdm_workflow",
    )
    parser.add_argument(
        "--queue",
        help="set the queue if using pbs.",
        default=None,
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
    parameters_set,
    parameters,
    pseudo_family,
    pseudos,
    only_valence,
    retrieve_hamiltonian,
    plot_wannier_functions,
    do_disentanglement,
    do_mlwf,
    write_u_matrices,
    soc,
    run_dft,
    group_name,
    daemon,
    system_2d,
    use_primitive_structure,
    cutoffs,
    kpoints_mesh,
    queue,
):
    codes = check_codes()

    group_name = update_group_name(
        group_name, only_valence, do_disentanglement, do_mlwf
    )

    if isinstance(structure_file, orm.StructureData):
        structure = structure_file
    else:
        structure = read_structure(structure_file)

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

    modifiers = {"parameters": parameters_set}
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
        "codes": codes,
        "structure": structure,
        "protocol": orm.Dict(dict={"name": protocol, "modifiers": modifiers}),
        "extra_parameters": orm.Dict(dict=parameters),
        "options": orm.Dict(
            dict={
                "resources": {
                    "num_machines": num_machines,
                    "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                },
                "max_wallclock_seconds": 3600 * 5,
                "withmpi": True,
                "queue_name": queue,
            }
        ),
        "system_2d": orm.Bool(system_2d),
        "use_primitive_structure": orm.Bool(use_primitive_structure),
    }

    controls = {
        "only_valence": orm.Bool(only_valence),
        "retrieve_hamiltonian": orm.Bool(retrieve_hamiltonian),
        "plot_wannier_functions": orm.Bool(plot_wannier_functions),
        "disentanglement": orm.Bool(do_disentanglement),
        "maximal_localisation": orm.Bool(do_mlwf),
        # optional
        "write_u_matrices": orm.Bool(write_u_matrices),
        "use_opengrid": orm.Bool(False),
        "compare_dft_bands": orm.Bool(run_dft),
        "spin_orbit_coupling": orm.Bool(soc),
    }

    wannier90_workchain_parameters.update(controls)

    if pseudo_family is not None:
        wannier90_workchain_parameters["pseudo_family"] = orm.Str(pseudo_family)
    if recommended_cutoffs is not None:
        wannier90_workchain_parameters["cutoffs"] = orm.Dict(
            dict=recommended_cutoffs
        )

    if kpoints_mesh is not None:
        try:
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(kpoints_mesh)
            wannier90_workchain_parameters["kpoints"] = kpoints
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {kpoints_mesh}\n{exception}"
            )

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
        args.parameters_set,
        args.parameters,
        args.pseudo_family,
        args.pseudos,
        args.only_valence,
        args.retrieve_hamiltonian,
        args.plot_wannier_functions,
        args.do_disentanglement,
        args.do_mlwf,
        args.write_u_matrices,
        args.soc,
        args.run_dft,
        args.group_name,
        args.daemon,
        args.system_2d,
        args.use_primitive_structure,
        args.cutoffs,
        args.kpoints_mesh,
        args.queue,
    )
