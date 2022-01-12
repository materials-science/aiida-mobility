from aiida.common.exceptions import NotExistent
from .. import cmd_launch
import click
from aiida import orm
from aiida.cmdline.utils import decorators
from ..utils import options
from ..utils import launch
from aiida_mobility.workflows.wannier.bands import Wannier90BandsWorkChain

str_pw = "pw"
str_pw2wan = "pw2wannier90"
str_projwfc = "projwfc"
str_wan = "wannier"
str_opengrid = "opengrid"


@cmd_launch.command("automated_wannier")
@options.STRUCTURE()
@options.PROTOCOL()
@options.PARAMETERS_SET()
@options.PARAMETERS()
@options.PSEUDO_FAMILY()
@click.option(
    "--only-valence",
    help="Compute only for valence bands (you must be careful to apply this only for insulators!)",
    is_flag=True,
    default=False,
)
@click.option(
    "--retrieve-hamiltonian",
    help="Retrieve Wannier Hamiltonian after the workflow finished",
    is_flag=True,
    default=False,
)
@click.option(
    "--plot-wannier-functions",
    help="Group name that the calculations will be added to.",
    is_flag=True,
    default=False,
)
@click.option(
    "--do-disentanglement",
    help="do disentanglement in Wanner90 step (This should be False, otherwise band structure is not optimal!)",
    is_flag=True,
    default=False,
)
@click.option(
    "--do-mlwf",
    help="do maximal localization of Wannier functions",
    is_flag=True,
    default=False,
)
@click.option(
    "--write-u-matrices",
    help="write u matrices",
    is_flag=True,
    default=False,
)
@options.SOC()
@options.SYSTEM_2D()
@options.USE_PRIMITIVE_STRUCTURE()
@options.CUTOFFS()
@options.KPOINTS_MESH()
@options.QUEUE_NAME()
@click.option(
    "--run-dft",
    help="Whether to run compare_dft_bands.",
    default=False,
    is_flag=True,
)
@options.COMPUTER(
    help=f"Computer that codes run on. <prerequisite: install codes you will run and set names to {str_pw}, {str_wan}, {str_pw2wan}, {str_projwfc}, {str_opengrid}.>"
)
@options.MAX_NUM_MACHINES()
@options.NUM_MPIPROCS_PER_MACHINE()
@options.DAEMON()
@decorators.with_dbenv()
def launch_automated_wannier(
    structure,
    protocol,
    parameters_set,
    parameters,
    pseudo_family,
    only_valence,
    retrieve_hamiltonian,
    plot_wannier_functions,
    do_disentanglement,
    do_mlwf,
    write_u_matrices,
    soc,
    system_2d,
    use_primitive_structure,
    cutoffs,
    kpoints_mesh,
    queue,
    run_dft,
    computer,
    max_num_machines,
    num_mpiprocs_per_machine,
    daemon,
):
    try:
        codes = dict(
            pw=orm.Code.get_from_string(f"{str_pw}@{computer}"),
            pw2wannier90=orm.Code.get_from_string(f"{str_pw2wan}@{computer}"),
            projwfc=orm.Code.get_from_string(f"{str_projwfc}@{computer}"),
            wannier90=orm.Code.get_from_string(f"{str_wan}@{computer}"),
        )
    except NotExistent as e:
        print(
            e,
            "Please modify the code labels in this script according to your machine",
        )
        exit(1)
    # optional code
    try:
        codes["opengrid"] = orm.Code.get_from_string(
            f"{str_opengrid}@{computer}"
        )
    except NotExistent:
        pass

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
                    "num_machines": max_num_machines,
                    "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
                },
                "max_wallclock_seconds": 3600 * 5,
                "withmpi": True,
                "queue_name": queue if queue is not None else "",
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
        wannier90_workchain_parameters["kpoints"] = kpoints_mesh

    launch.launch_process(
        Wannier90BandsWorkChain, daemon, **wannier90_workchain_parameters
    )