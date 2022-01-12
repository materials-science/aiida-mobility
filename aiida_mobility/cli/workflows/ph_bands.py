from aiida_mobility.utils import (
    get_metadata_options,
    get_protocol,
    get_pw_common_inputs,
)
from aiida_mobility.workflows.ph.bands import PhBandsWorkChain
from .. import cmd_launch
import click
from aiida import orm
from aiida.cmdline.utils import decorators
from ..utils import options
from ..utils import launch

str_pw = "pw"
str_ph = "ph"
str_q2r = "q2r"
str_matdyn = "matdyn"


@cmd_launch.command("ph_bands")
@options.STRUCTURE()
@options.PROTOCOL()
@options.PARAMETERS_SET()
@options.PARAMETERS()
@options.PSEUDO_FAMILY()
@options.KPOINTS_MESH()
@options.CUTOFFS()
@options.SYSTEM_2D()
@options.RUN_RELAX()
@options.VC_RELAX()
# ph settings
@click.option(
    "--tr2_ph",
    type=float,
    help="tr2_ph, default is 1.0e-15",
    default=1.0e-15,
)
@click.option(
    "--check-imaginary-frequencies",
    help="Whether to check imaginary frequencies, if it is True, the Calculation will throw an error when imaginary frequencies are found.",
    is_flag=True,
    default=False,
)
@click.option(
    "--frequency-threshold",
    type=float,
    help="tolerable frequency threshold for checking imaginray frequencies, default is -20",
    default=-20,
)
@click.option(
    "--separated-qpoints",
    help="Set true if you want to calculate each qpoint separately.",
    is_flag=True,
    default=False,
)
@options.PH_EPSIL()
@options.QPOINTS_MESH()
@options.QPOINTS_DISTANCE()
@options.MAX_WALLCLOCK_SECONDS(default=24 * 3600)
@options.Q2R_ZASR()
@options.MATDYN_ASR()
@options.MATDYN_DISTANCE()
@options.MAX_RESTART_ITERATIONS()
@options.SOC()
@options.QUEUE_NAME()
@options.COMPUTER(
    help=f"Computer that codes run on. <prerequisite: install codes you will run and set names to {str_pw}, {str_ph}, {str_q2r}, {str_matdyn}.>"
)
@options.MAX_NUM_MACHINES()
@options.NUM_MPIPROCS_PER_MACHINE()
@options.DAEMON()
@decorators.with_dbenv()
def launch_ph_bands(
    structure,
    protocol,
    parameters_set,
    parameters,
    pseudo_family,
    kpoints_mesh,
    cutoffs,
    system_2d,
    run_relax,
    vc_relax,
    tr2_ph,
    check_imaginary_frequencies,
    frequency_threshold,
    separated_qpoints,
    epsil,
    qpoints_mesh,
    qpoints_distance,
    max_wallclock_seconds,
    q2r_zasr,
    matdyn_asr,
    matdyn_distance,
    max_restart_iterations,
    soc,
    queue,
    computer,
    max_num_machines,
    num_mpiprocs_per_machine,
    daemon,
):
    print("running ph bands workflow for {}".format(structure.get_formula()))

    pw_code = orm.Code.get_from_string(f"{str_pw}@{computer}")
    ph_code = orm.Code.get_from_string(f"{str_ph}@{computer}")
    q2r_code = orm.Code.get_from_string(f"{str_q2r}@{computer}")
    matdyn_code = orm.Code.get_from_string(f"{str_matdyn}@{computer}")

    protocol, recommended_cutoffs = get_protocol(
        structure, parameters_set, protocol
    )

    protocol.update(parameters)
    if soc:
        protocol.update({"lspinorb": True, "noncolin": True})

    workchain_parameters = {
        "structure": structure,
        "max_restart_iterations": orm.Int(max_restart_iterations),
    }

    if run_relax:
        relax_mode = "vc-relax" if vc_relax else "relax"
        relax_parameters = {
            "base": get_pw_common_inputs(
                structure,
                pw_code,
                protocol,
                recommended_cutoffs,
                pseudo_family,
                cutoffs,
                system_2d,
                max_num_machines,
                num_mpiprocs_per_machine,
                mode=relax_mode,
                walltime=max_wallclock_seconds,
                queue_name=queue,
            ),
            "relaxation_scheme": orm.Str(relax_mode),
            # "max_meta_convergence_iterations": orm.Int(10),
            "meta_convergence": orm.Bool(
                protocol.get("meta_convergence", True)
            ),
            "volume_convergence": orm.Float(
                protocol.get("volume_convergence", 0.01)
            ),
        }
        parameters = relax_parameters["base"]["pw"]["parameters"].get_dict()
        press_conv_thr = protocol.get("press_conv_thr")
        if press_conv_thr is not None:
            parameters.setdefault("CELL", {"press_conv_thr": press_conv_thr})
        relax_parameters["base"]["pw"]["parameters"] = orm.Dict(dict=parameters)
        if kpoints_mesh is not None:
            relax_parameters["base"]["kpoints"] = kpoints_mesh
        workchain_parameters["relax"] = relax_parameters

    scf_parameters = get_pw_common_inputs(
        structure,
        pw_code,
        protocol,
        recommended_cutoffs,
        pseudo_family,
        cutoffs,
        system_2d,
        max_num_machines,
        num_mpiprocs_per_machine,
        walltime=max_wallclock_seconds,
        queue_name=queue,
    )
    if kpoints_mesh is not None:
        scf_parameters["kpoints"] = kpoints_mesh
    workchain_parameters["scf"] = scf_parameters

    ph_calculation_parameters = {
        "code": ph_code,
        "parameters": orm.Dict(
            dict={
                "INPUTPH": {
                    "tr2_ph": tr2_ph,
                    "epsil": epsil,
                    "lqdir": True,
                }
            }
        ),
        "metadata": {
            "options": get_metadata_options(
                max_num_machines,
                num_mpiprocs_per_machine,
                walltime=max_wallclock_seconds,
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
        workchain_parameters["qpoints"] = qpoints_mesh
    else:
        workchain_parameters["qpoints_distance"] = orm.Float(qpoints_distance)
    workchain_parameters["system_2d"] = orm.Bool(system_2d)

    q2r_calculation_parameters = {
        "code": q2r_code,
        "parameters": orm.Dict(dict={"INPUT": {"zasr": q2r_zasr}}),
        "metadata": {
            "options": get_metadata_options(
                max_num_machines, num_mpiprocs_per_machine, queue_name=queue
            )
        },
    }
    workchain_parameters["q2r"] = {"q2r": q2r_calculation_parameters}

    matdyn_calculation_parameters = {
        "code": matdyn_code,
        "parameters": orm.Dict(dict={"INPUT": {"asr": matdyn_asr}}),
        "metadata": {
            "options": get_metadata_options(
                max_num_machines, num_mpiprocs_per_machine, queue_name=queue
            )
        },
    }
    workchain_parameters["matdyn"] = {"matdyn": matdyn_calculation_parameters}
    workchain_parameters["matdyn_distance"] = orm.Float(
        matdyn_distance
        if matdyn_distance is not None
        else protocol.get("kpoints_distance_for_bands", 0.01)
    )

    launch.launch_process(PhBandsWorkChain, daemon, **workchain_parameters)