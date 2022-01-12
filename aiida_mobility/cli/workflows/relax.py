from aiida_mobility.workflows.pw.relax import PwRelaxWorkChain
from aiida_mobility.utils import (
    get_protocol,
    get_pw_common_inputs,
)
from .. import cmd_launch
from aiida import orm
from aiida.cmdline.utils import decorators
from aiida.cmdline.params import options as options_core
from ..utils import options
from ..utils import launch

# Please modify these according to your machine
code_str = "pw"


@cmd_launch.command("relax")
@options.STRUCTURE()
@options.PROTOCOL()
@options.PARAMETERS_SET()
@options.PARAMETERS()
@options.PSEUDO_FAMILY()
@options.KPOINTS_MESH()
@options.CUTOFFS()
@options.SYSTEM_2D()
@options.VC_RELAX()
@options.SOC()
@options.QUEUE_NAME()
@options.COMPUTER(
    help=f"Computer that codes run on. <prerequisite: install codes you will run and set names to {code_str}.>"
)
@options.MAX_WALLCLOCK_SECONDS(default=24 * 3600)
@options.MAX_NUM_MACHINES()
@options.NUM_MPIPROCS_PER_MACHINE()
@options.DAEMON()
@decorators.with_dbenv()
def launch_relax(
    structure,
    protocol,
    parameters_set,
    parameters,
    pseudo_family,
    kpoints_mesh,
    cutoffs,
    system_2d,
    vc_relax,
    soc,
    queue,
    computer,
    max_wallclock_seconds,
    max_num_machines,
    num_mpiprocs_per_machine,
    daemon,
):
    print(
        "running relax structure calculation for {}".format(
            structure.get_formula()
        )
    )

    pw_code = code_str + "@{}".format(computer)

    protocol, recommended_cutoffs = get_protocol(
        structure, parameters_set, protocol
    )
    protocol.update(parameters)
    if soc:
        protocol.update({"lspinorb": True, "noncolin": True})

    # Submit the Relax workchain
    relax_mode = "vc-relax" if vc_relax else "relax"
    relax_workchain_parameters = {
        "structure": structure,
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
        "meta_convergence": orm.Bool(protocol["meta_convergence"]),
        # "max_meta_convergence_iterations": orm.Int(10),
        "volume_convergence": orm.Float(protocol["volume_convergence"]),
        "system_2d": orm.Bool(system_2d),
    }

    if kpoints_mesh is not None:
        relax_workchain_parameters["base"]["kpoints"] = kpoints_mesh

    launch.launch_process(
        PwRelaxWorkChain, daemon, **relax_workchain_parameters
    )