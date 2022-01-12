from .. import cmd_launch
import click
from aiida.orm.utils import load_node
from aiida import orm
from aiida.cmdline.utils import decorators
from aiida.cmdline.params import options as options_core
from aiida.plugins import WorkflowFactory
from ..utils import options
from ..utils import launch


@cmd_launch.command("perturbo")
@click.option(
    "--ph",
    required=True,
    type=int,
    help="The PK of the PhCalculation or PhBaseWorkChain.",
)
@click.option(
    "--nscf",
    required=True,
    type=int,
    help="The PK of the PwCalculation or PwBaseWorkChain.",
)
@click.option(
    "--wannier",
    required=True,
    type=int,
    help="The PK of the Wannier90Calculation or Wannier90BaseWorkChain.",
)
@click.option(
    "--bands-energy-distance",
    type=float,
    help="Energy range of considered bands (e.g. fermi energy +/- 0.3, defalut is 0.3).",
)
@click.option(
    "--temperature",
    type=int,
    nargs=2,
    default=None,
    help="[Min temperature, Max temperature, temperature step]. If not set, 300K will be used.",
)
@click.option(
    "--carrier-concentration",
    type=float,
    help="Carrier concentration.",
)
@click.option(
    "--phfreq-cutoff",
    type=float,
    help="the cutoff energy for the phonons. Phonon with their energy smaller than the cutoff (in meV) is ignored; 0.5-2 meV is recommended.",
)
@click.option(
    "--delta-smear",
    type=float,
    help="the broadening (in meV) used for the Gaussian function used to model the Dirac delta function.",
)
@click.option(
    "--sampling",
    type=str,
    help="sampling method for random q points used in e-ph self-energy calculation, `uniform` and `cauchy`[useful for polar materials] are available. If not set, `fqlist` will be same with `fklist`.",
)
@click.option(
    "--nsamples",
    type=int,
    help="Number of q-points for the summation over the q-points in imsigma calculation.",
)
@click.option(
    "--cauchy-scale",
    type=float,
    help="Scale parameter gamma for the Cauchy distribution; used when sampling='cauchy'.",
)
@click.option(
    "--boltz-nstep",
    type=int,
    help="Contains the maximum number of iterations in the iterative scheme for solving Boltzmann equation. Default is `0`, which uses RTA.",
)
@options.SYSTEM_2D()
@options_core.CODES(help="qe2pert code, perturbo code")
@options.MAX_NUM_MACHINES()
@options.NUM_MPIPROCS_PER_MACHINE()
@options.DAEMON()
@options.CLEAN_WORKDIR()
@decorators.with_dbenv()
def launch_perturbo(
    ph,
    nscf,
    wannier,
    bands_energy_threshold,
    temperature,
    carrier_concentration,
    phfreq_cutoff,
    delta_smear,
    sampling,
    nsamples,
    cauchy_scale,
    boltz_nstep,
    system_2d,
    codes,
    max_num_machines,
    num_mpiprocs_per_machine,
    daemon,
    clean_workdir,
):
    ph_node = load_node(ph)
    nscf_node = load_node(nscf)
    wannier_node = load_node(wannier)
    inputs = {
        "qe2pert": {
            "code": codes[0],
            "ph_folder": ph_node.outputs.remote_folder,
            "nscf_folder": nscf_node.outputs.remote_folder,
            "wannier_folder": wannier_node.outputs.remote_folder,
            "system_2d": orm.Bool(system_2d),
        },
        "pert_code": codes[1],
        "clean_workdir": orm.Bool(clean_workdir),
        "metadata": {
            "description": "Perturbo workflow",
        },
        "metadata_options": orm.Dict(
            dict={
                "resources": {
                    "num_machines": int(max_num_machines),
                    "num_mpiprocs_per_machine": int(num_mpiprocs_per_machine),
                },
                "withmpi": True,
            }
        ),
    }

    if bands_energy_threshold is not None:
        inputs["bands_energy_threshold"] = orm.Float(bands_energy_threshold)
    if temperature is not None and len(temperature) == 3:
        inputs["min_T"] = orm.Int(temperature[0])
        inputs["max_T"] = orm.Int(temperature[1])
        inputs["T_step"] = orm.Int(temperature[2])
    if carrier_concentration is not None:
        inputs["carrier_concentration"] = orm.Float(carrier_concentration)
    if phfreq_cutoff is not None:
        inputs["phfreq_cutoff"] = orm.Int(phfreq_cutoff)
    if delta_smear is not None:
        inputs["delta_smear"] = orm.Float(delta_smear)
    if sampling is not None:
        inputs["sampling"] = orm.Str(sampling)
    if nsamples is not None:
        inputs["nsamples"] = orm.Int(nsamples)
    if cauchy_scale is not None:
        inputs["cauchy_scale"] = orm.Float(cauchy_scale)
    if boltz_nstep is not None:
        inputs["boltz_nstep"] = orm.Int(boltz_nstep)

    launch.launch_process(
        WorkflowFactory("mobility.perturbo"), daemon, **inputs
    )