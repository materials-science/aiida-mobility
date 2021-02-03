#!/usr/bin/env runaiida
import argparse
from aiida.engine.launch import submit, run_get_pk
from aiida.common.extendeddicts import AttributeDict
from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_dict
from aiida_mobility.utils.protocols.pw import ProtocolManager
from aiida_mobility.utils import (
    add_to_group,
    print_help,
    read_structure,
    write_pk_to_file,
)
from aiida_mobility.workflows.matdyn.matdyn_restart import (
    MatdynRestartWorkChain,
)

from aiida import orm

str_pw = "qe-6.5-pw"
str_ph = "qe-6.5-ph"
str_q2r = "qe-6.5-q2r"
str_matdyn = "qe-6.5-matdyn"


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA workflows to automatically compute the Phono Dispersion."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    parser.add_argument(
        "-S",
        "--structure",
        metavar="FILENAME",
        help="path to an input Structure(xsf,cif,poscar) file",
    )
    # scf parameters
    parser.add_argument(
        "-p",
        "--parameters",
        help="available scf parameters protocols are {`fast`, `default` and `accurate`}_{``, `gaussian`, `fixed`}",
        default="default_fixed",
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
        "--run-relax",
        default=False,
        help="Whether to run relax before scf.",
        action="store_true",
    )
    # ph parameters
    parser.add_argument(
        "--tr2_ph", type=float, help="tr2_ph, default is 1.0e-8", default=1.0e-8
    )
    parser.add_argument(
        "--epsil", type=bool, help="epsil, default is True", default=True
    )
    parser.add_argument(
        "--qpoints_distance",
        type=float,
        help="qpoint distance to get qpoints, default is 0.2",
        default=0.2,
    )
    parser.add_argument(
        "--walltime",
        type=int,
        help="the max wall time(hours) of calculation. default is 24 hours.",
        default=24,
    )
    # q2r parameters
    parser.add_argument(
        "--zasr",
        type=str,
        default="crystal",
        help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
    )
    # matdyn parameters
    parser.add_argument(
        "--asr",
        type=str,
        default="crystal",
        help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
    )
    parser.add_argument(
        "--matdyn_distance",
        type=float,
        help="kpoint distance to get kpoints, default is 0.01",
        default=0.01,
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
        default="ph_workflow",
    )
    args = parser.parse_args()
    if args.cutoffs is not None and args.pseudos is not None:
        print("[Warning]: cutoffs will replace the cutoffs in pseudos data.")
    return args


def get_protocol(structure, scf_parameters_name, protocol, pseudos):
    # get custom pseudo
    modifiers = {"parameters": scf_parameters_name}
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
    # get protocol
    protocol_manager = ProtocolManager(protocol)
    protocol_modifiers = modifiers
    protocol = protocol_manager.get_protocol_data(modifiers=protocol_modifiers)

    return protocol, recommended_cutoffs


def get_pw_common_inputs(
    structure,
    pw_code,
    protocol,
    recommended_cutoffs,
    pseudo_family,
    cutoffs,
    set_2d_mesh,
    num_machines,
    num_mpiprocs_per_machine,
):
    # get cutoff
    ecutwfc = []
    ecutrho = []
    if cutoffs is not None and len(cutoffs) == 2:
        cutoff = cutoffs[0]
        dual = cutoffs[1]
        cutrho = cutoff * dual
        ecutwfc.append(cutoff)
        ecutrho.append(cutrho)
    elif recommended_cutoffs is not None:
        cutoff = recommended_cutoffs["cutoff"]
        dual = recommended_cutoffs["dual"]
        cutrho = cutoff * dual
        ecutwfc.append(cutoff)
        ecutrho.append(cutrho)
    else:
        for kind in structure.get_kind_names():
            try:
                cutoff = protocol["pseudo_data"][kind]["cutoff"]
                dual = protocol["pseudo_data"][kind]["dual"]
                cutrho = dual * cutoff
                ecutwfc.append(cutoff)
                ecutrho.append(cutrho)
            except KeyError:
                raise SystemExit(
                    "failed to retrieve the cutoff or dual factor for {}".format(
                        kind
                    )
                )

    number_of_atoms = len(structure.sites)
    pw_parameters = {
        "CONTROL": {
            "restart_mode": "from_scratch",
            "tstress": protocol["tstress"],
            "tprnfor": protocol["tprnfor"],
            "etot_conv_thr": protocol["convergence_threshold_per_atom"]
            * number_of_atoms
            * 10,
            "forc_conv_thr": protocol["convergence_threshold_per_atom"]
            * number_of_atoms
            * 10,
        },
        "SYSTEM": {
            "ecutwfc": max(ecutwfc),
            "ecutrho": max(ecutrho),
        },
        "ELECTRONS": {
            "conv_thr": protocol["convergence_threshold_per_atom"]
            * number_of_atoms,
        },
    }

    if "smearing" in protocol:
        pw_parameters["SYSTEM"]["smearing"] = protocol["smearing"]
    if "degauss" in protocol:
        pw_parameters["SYSTEM"]["degauss"] = protocol["degauss"]
    if "occupations" in protocol:
        pw_parameters["SYSTEM"]["occupations"] = protocol["occupations"]

    inputs = AttributeDict(
        {
            "pw": {
                "code": orm.load_code(pw_code),
                "parameters": orm.Dict(dict=pw_parameters),
                "metadata": {},
            }
        }
    )

    if pseudo_family is not None:
        inputs["pseudo_family"] = orm.Str(pseudo_family)
    else:
        checked_pseudos = protocol.check_pseudos(
            modifier_name=protocol.modifiers.get("pseudo", None),
            pseudo_data=protocol.modifiers.get("pseudo_data", None),
        )
        known_pseudos = checked_pseudos["found"]
        inputs.pw["pseudos"] = get_pseudos_from_dict(structure, known_pseudos)
    if set_2d_mesh:
        inputs["set_2d_mesh"] = orm.Bool(set_2d_mesh)

    inputs.kpoints_distance = orm.Float(protocol["kpoints_mesh_density"])

    inputs.pw.metadata.options = get_options(
        num_machines, num_mpiprocs_per_machine
    )

    # return scf_parameters
    return inputs


def get_options(num_machines, num_mpiprocs_per_machine, walltime=5):
    return {
        "resources": {
            "num_machines": num_machines,
            "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
        },
        "max_wallclock_seconds": 3600 * walltime,
        "withmpi": True,
    }


def submit_workchain(
    structure_file,
    scf_parameters_name,
    protocol,
    pseudos,
    pseudo_family,
    cutoffs,
    set_2d_mesh,
    run_relax,
    tr2_ph,
    epsil,
    qpoints_distance,
    walltime,
    zasr,
    asr,
    matdyn_distance,
    num_machines,
    num_mpiprocs_per_machine,
    pw_code,
    ph_code,
    q2r_code,
    matdyn_code,
    daemon,
    group_name,
):
    if isinstance(structure_file, orm.StructureData):
        structure = structure_file
    else:
        structure = read_structure(structure_file)
    print("running matdyn workflow for {}".format(structure.get_formula()))

    protocol, recommended_cutoffs = get_protocol(
        structure, scf_parameters_name, protocol, pseudos
    )

    workchain_parameters = {"structure": structure}

    scf_parameters = get_pw_common_inputs(
        structure,
        pw_code,
        protocol,
        recommended_cutoffs,
        pseudo_family,
        cutoffs,
        set_2d_mesh,
        num_machines,
        num_mpiprocs_per_machine,
    )
    workchain_parameters["scf"] = scf_parameters

    if run_relax:
        relax_parameters = {
            "base": get_pw_common_inputs(
                structure,
                pw_code,
                protocol,
                recommended_cutoffs,
                pseudo_family,
                cutoffs,
                set_2d_mesh,
                num_machines,
                num_mpiprocs_per_machine,
            ),
            "relaxation_scheme": orm.Str("vc-relax"),
            "meta_convergence": orm.Bool(protocol["meta_convergence"]),
            "volume_convergence": orm.Float(protocol["volume_convergence"]),
        }
        parameters = relax_parameters["base"]["pw"]["parameters"].get_dict()
        parameters.setdefault(
            "CELL", {"press_conv_thr": protocol["press_conv_thr"]}
        )
        relax_parameters["base"]["pw"]["parameters"] = orm.Dict(dict=parameters)
        workchain_parameters["relax"] = relax_parameters

    ph_calculation_parameters = {
        "code": orm.Code.get_from_string(ph_code),
        "parameters": orm.Dict(
            dict={
                "INPUTPH": {
                    "tr2_ph": tr2_ph,
                    "epsil": epsil,
                }
            }
        ),
        "metadata": {
            "options": get_options(
                num_machines, num_mpiprocs_per_machine, walltime
            )
        },
    }
    workchain_parameters["ph"] = {"ph": ph_calculation_parameters}
    workchain_parameters["qpoints_distance"] = orm.Float(qpoints_distance)
    workchain_parameters["set_2d_mesh"] = orm.Bool(set_2d_mesh)

    q2r_calculation_parameters = {
        "code": orm.Code.get_from_string(q2r_code),
        "parameters": orm.Dict(dict={"INPUT": {"zasr": zasr}}),
        "metadata": {
            "options": get_options(num_machines, num_mpiprocs_per_machine)
        },
    }
    workchain_parameters["q2r"] = {"q2r": q2r_calculation_parameters}

    matdyn_calculation_parameters = {
        "code": orm.Code.get_from_string(matdyn_code),
        "parameters": orm.Dict(dict={"INPUT": {"asr": asr}}),
        "metadata": {
            "options": get_options(num_machines, num_mpiprocs_per_machine)
        },
    }
    workchain_parameters["matdyn"] = {"matdyn": matdyn_calculation_parameters}
    workchain_parameters["matdyn_distance"] = orm.Float(matdyn_distance)

    if daemon is not None:
        workchain = submit(MatdynRestartWorkChain, **workchain_parameters)
    else:
        workchain = run_get_pk(MatdynRestartWorkChain, **workchain_parameters)

    add_to_group(workchain, group_name)
    print_help(workchain, structure)
    write_pk_to_file(workchain, structure, "phono")


if __name__ == "__main__":
    args = parse_arugments()
    str_pw += "@{}".format(args.computer)
    str_ph += "@{}".format(args.computer)
    str_q2r += "@{}".format(args.computer)
    str_matdyn += "@{}".format(args.computer)
    submit_workchain(
        args.structure,
        args.parameters,
        args.protocol,
        args.pseudos,
        args.pseudo_family,
        args.cutoffs,
        args.set_2d_mesh,
        args.run_relax,
        args.tr2_ph,
        args.epsil,
        args.qpoints_distance,
        args.walltime,
        args.zasr,
        args.asr,
        args.matdyn_distance,
        args.num_machines,
        args.num_mpiprocs_per_machine,
        str_pw,
        str_ph,
        str_q2r,
        str_matdyn,
        args.daemon,
        args.group_name,
    )
