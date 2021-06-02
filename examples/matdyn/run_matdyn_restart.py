#!/usr/bin/env runaiida
import argparse
from aiida.engine.launch import submit, run_get_pk
from aiida_mobility.utils import (
    add_to_group,
    get_metadata_options,
    get_protocol,
    get_pw_common_inputs,
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
        help="available protocols are 'theos-ht-1.0', 'ms-1.0', and 'testing'",
        default="ms-1.0",
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
        "--run-relax",
        default=False,
        help="Whether to run relax before scf.",
        action="store_true",
    )
    # ph parameters
    parser.add_argument(
        "--tr2_ph",
        type=float,
        help="tr2_ph, default is 1.0e-15",
        default=1.0e-15,
    )
    parser.add_argument(
        "--check-imaginary-frequencies",
        default=False,
        help="Whether to check imaginary frequencies.",
        action="store_true",
    )
    parser.add_argument(
        "--frequency-threshold",
        type=float,
        help="frequency_threshold, default is -20",
        default=-20,
    )
    parser.add_argument(
        "--separated-qpoints",
        default=False,
        action="store_true",
        help="Set true if you want to calculate each qpoint separately.",
    )
    parser.add_argument(
        "--epsil",
        help="epsil, default is False",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--qpoints-mesh",
        nargs=3,
        type=int,
        help="The number of points in the qpoint mesh along each basis vector.",
    )
    parser.add_argument(
        "--qpoints-distance",
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
        "--matdyn-distance",
        type=float,
        help="kpoint distance to get kpoints, default is 0.01",
        default=0.01,
    )
    parser.add_argument(
        "-N", "--num-machines", type=int, help="number of machines", default=1
    )
    parser.add_argument(
        "-P",
        "--num-mpiprocs-per-machine",
        type=int,
        help="number of mpiprocs per machine",
        default=8,
    )
    parser.add_argument("-C", "--computer", type=str, default="qe")
    parser.add_argument(
        "--max-restart-iterations",
        type=int,
        help="max_restart_iterations",
        default=1,
    )
    parser.add_argument(
        "--queue",
        help="set the queue if using pbs.",
        default=None,
    )
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
        default="ph_workflow",
    )
    args = parser.parse_args()
    if args.cutoffs is not None and args.pseudos is not None:
        print("[Warning]: cutoffs will replace the cutoffs in pseudos data.")
    return args


def submit_workchain(
    structure_file,
    scf_parameters_name,
    protocol,
    pseudos,
    pseudo_family,
    kpoints_mesh,
    cutoffs,
    system_2d,
    run_relax,
    tr2_ph,
    check_imaginary_frequencies,
    frequency_threshold,
    separated_qpoints,
    epsil,
    qpoints_mesh,
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
    max_restart_iterations,
    queue,
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

    workchain_parameters = {
        "structure": structure,
        "max_restart_iterations": orm.Int(max_restart_iterations),
    }

    kpoints = None
    if kpoints_mesh is not None:
        try:
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(kpoints_mesh)
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {kpoints_mesh}\n{exception}"
            )

    if run_relax:
        relax_parameters = {
            "base": get_pw_common_inputs(
                structure,
                pw_code,
                protocol,
                recommended_cutoffs,
                pseudo_family,
                cutoffs,
                system_2d,
                num_machines,
                num_mpiprocs_per_machine,
                mode="vc-relax",
                queue_name=queue,
            ),
            "relaxation_scheme": orm.Str("vc-relax"),
            "meta_convergence": orm.Bool(protocol["meta_convergence"]),
            # "max_meta_convergence_iterations": orm.Int(10),
            "volume_convergence": orm.Float(protocol["volume_convergence"]),
        }
        parameters = relax_parameters["base"]["pw"]["parameters"].get_dict()
        parameters.setdefault(
            "CELL", {"press_conv_thr": protocol["press_conv_thr"]}
        )
        relax_parameters["base"]["pw"]["parameters"] = orm.Dict(dict=parameters)
        if kpoints is not None:
            relax_parameters["base"]["kpoints"] = kpoints
        workchain_parameters["relax"] = relax_parameters

    scf_parameters = get_pw_common_inputs(
        structure,
        pw_code,
        protocol,
        recommended_cutoffs,
        pseudo_family,
        cutoffs,
        system_2d,
        num_machines,
        num_mpiprocs_per_machine,
        queue_name=queue,
    )
    if kpoints is not None:
        scf_parameters["kpoints"] = kpoints
    workchain_parameters["scf"] = scf_parameters

    ph_calculation_parameters = {
        "code": orm.Code.get_from_string(ph_code),
        "parameters": orm.Dict(
            dict={
                "INPUTPH": {
                    "tr2_ph": tr2_ph,
                    "epsil": epsil,
                    "lqdir": True,
                    "fildvscf": "dvscf",
                    # perturbo needs files in xml format
                    # but aiida-quantumespresso cannot set fildyn
                    # "fildyn": "dyn.xml",
                }
            }
        ),
        "metadata": {
            "options": get_metadata_options(
                num_machines,
                num_mpiprocs_per_machine,
                walltime,
                queue_name=queue,
            )
        },
    }
    workchain_parameters["ph"] = {
        "ph": ph_calculation_parameters,
        "check_imaginary_frequencies": orm.Bool(check_imaginary_frequencies),
        "frequency_threshold": orm.Float(frequency_threshold),
        "separated_qpoints": orm.Bool(separated_qpoints),
    }
    if qpoints_mesh is not None:
        try:
            qpoints = orm.KpointsData()
            qpoints.set_kpoints_mesh(qpoints_mesh)
            workchain_parameters["qpoints"] = qpoints
        except ValueError as exception:
            raise SystemExit(
                f"failed to create a KpointsData mesh out of {qpoints_mesh}\n{exception}"
            )
    else:
        workchain_parameters["qpoints_distance"] = orm.Float(qpoints_distance)
    workchain_parameters["system_2d"] = orm.Bool(system_2d)

    q2r_calculation_parameters = {
        "code": orm.Code.get_from_string(q2r_code),
        "parameters": orm.Dict(dict={"INPUT": {"zasr": zasr}}),
        "metadata": {
            "options": get_metadata_options(
                num_machines, num_mpiprocs_per_machine, queue_name=queue
            )
        },
    }
    workchain_parameters["q2r"] = {"q2r": q2r_calculation_parameters}

    matdyn_calculation_parameters = {
        "code": orm.Code.get_from_string(matdyn_code),
        "parameters": orm.Dict(dict={"INPUT": {"asr": asr}}),
        "metadata": {
            "options": get_metadata_options(
                num_machines, num_mpiprocs_per_machine, queue_name=queue
            )
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
        args.kpoints_mesh,
        args.cutoffs,
        args.system_2d,
        args.run_relax,
        args.tr2_ph,
        args.check_imaginary_frequencies,
        args.frequency_threshold,
        args.separated_qpoints,
        args.epsil,
        args.qpoints_mesh,
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
        args.max_restart_iterations,
        args.queue,
        args.daemon,
        args.group_name,
    )
