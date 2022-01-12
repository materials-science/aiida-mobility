# -*- coding: utf-8 -*-
"""Pre-defined overridable options for commonly used command line interface parameters."""
from aiida import orm
from aiida_mobility.utils import read_structure
from ase.atoms import default
import click

from aiida.cmdline.params import types
from aiida.cmdline.params.options import OverridableOption
from aiida.cmdline.utils import decorators
from aiida.common import exceptions

from . import validate


class StructureParamType(click.ParamType):
    name = "structure"

    def convert(self, value, param, ctx):
        try:
            if isinstance(value, orm.StructureData):
                return value
            else:
                return read_structure(value)
        except Exception:
            self.fail(
                "expected structure node or structure file",
                param,
                ctx,
            )


def StoreKeyPairParam(ctx, param, value):
    my_dict = {}
    for arg in value:
        k, v = arg.split("=", 1)
        if v in ["True", "true"]:
            my_dict[k] = True
        elif v in ["False", "false"]:
            my_dict[k] = False
        else:
            try:
                my_dict[k] = int(v)
            except ValueError:
                try:
                    my_dict[k] = float(v)
                except ValueError:
                    my_dict[k] = v
    return my_dict


STRUCTURE = OverridableOption(
    "-S",
    "--structure",
    type=StructureParamType(),
    help="StructureData node or Structure file(xsf,cif,poscar).",
)

KPOINTS_DISTANCE = OverridableOption(
    "--kpoints-distance",
    type=click.FLOAT,
    default=0.5,
    show_default=True,
    help="The minimal distance between k-points in reciprocal space in inverse Ångström.",
)

KPOINTS_MESH = OverridableOption(
    "--kpoints-mesh",
    "kpoints_mesh",
    nargs=3,
    type=click.INT,
    default=None,
    show_default=True,
    callback=validate.validate_kpoints_mesh,
    help="The number of points in the kpoint mesh along each basis vector.",
)

QPOINTS_MESH = OverridableOption(
    "--qpoints-mesh",
    "qpoints_mesh",
    nargs=3,
    type=click.INT,
    show_default=True,
    callback=validate.validate_kpoints_mesh,
    help="The number of points in the qpoint mesh along each basis vector.",
)

QPOINTS_DISTANCE = OverridableOption(
    "--qpoints-distance",
    type=click.FLOAT,
    default=0.5,
    show_default=True,
    help="The minimal distance between k-points in reciprocal space in inverse Ångström.",
)

MAX_NUM_MACHINES = OverridableOption(
    "-m",
    "--max-num-machines",
    type=click.INT,
    default=1,
    show_default=True,
    help="The maximum number of machines (nodes) to use for the calculations.",
)

MAX_WALLCLOCK_SECONDS = OverridableOption(
    "-w",
    "--max-wallclock-seconds",
    type=click.INT,
    default=1800,
    show_default=True,
    help="the maximum wallclock time in seconds to set for the calculations.",
)

WITH_MPI = OverridableOption(
    "-i",
    "--with-mpi",
    is_flag=True,
    default=True,
    show_default=True,
    help="Run the calculations with MPI enabled.",
)

NUM_MPIPROCS_PER_MACHINE = OverridableOption(
    "-np",
    "--num-mpiprocs-per-machine",
    type=click.INT,
    default=1,
    show_default=True,
    help="The number of process per machine (node) to use for the calculations.",
)
QUEUE_NAME = OverridableOption(
    "--queue",
    default=None,
    show_default=True,
    help="The queue of PBS system.",
)


# PARENT_FOLDER = OverridableOption(
#     "-P",
#     "--parent-folder",
#     "parent_folder",
#     type=types.DataParamType(sub_classes=("aiida.data:remote",)),
#     show_default=True,
#     required=False,
#     help="The PK of a parent remote folder (for restarts).",
# )

DAEMON = OverridableOption(
    "-d",
    "--daemon",
    is_flag=True,
    default=False,
    show_default=True,
    help="Submit the process to the daemon instead of running it locally.",
)

CLEAN_WORKDIR = OverridableOption(
    "-x",
    "--clean-workdir",
    is_flag=True,
    default=False,
    show_default=True,
    help="Clean the remote folder of all the launched calculations after completion of the workchain.",
)

MAX_RESTART_ITERATIONS = OverridableOption(
    "--max-restart-iterations",
    type=int,
    help="max restart iterations",
    default=1,
)


# AUTOMATIC_PARALLELIZATION = OverridableOption(
#     "-a",
#     "--automatic-parallelization",
#     is_flag=True,
#     default=False,
#     show_default=True,
#     help="Enable the automatic parallelization option of the workchain.",
# )

# ECUTWFC = OverridableOption(
#     "-W",
#     "--ecutwfc",
#     type=click.FLOAT,
#     help="The plane wave cutoff energy in Ry.",
# )

# ECUTRHO = OverridableOption(
#     "-R",
#     "--ecutrho",
#     type=click.FLOAT,
#     help="The charge density cutoff energy in Ry.",
# )

# HUBBARD_U = OverridableOption(
#     "-U",
#     "--hubbard-u",
#     nargs=2,
#     multiple=True,
#     type=click.Tuple([str, float]),
#     help="Add a Hubbard U term to a specific kind.",
#     metavar="<KIND MAGNITUDE>...",
# )

# HUBBARD_V = OverridableOption(
#     "-V",
#     "--hubbard-v",
#     nargs=4,
#     multiple=True,
#     type=click.Tuple([int, int, int, float]),
#     help="Add a Hubbard V interaction between two sites.",
#     metavar="<SITE SITE TYPE MAGNITUDE>...",
# )

# HUBBARD_FILE = OverridableOption(
#     "-H",
#     "--hubbard-file",
#     "hubbard_file_pk",
#     type=types.DataParamType(sub_classes=("aiida.data:singlefile",)),
#     help="SinglefileData containing Hubbard parameters from a HpCalculation to use as input for Hubbard V.",
# )

# STARTING_MAGNETIZATION = OverridableOption(
#     "--starting-magnetization",
#     nargs=2,
#     multiple=True,
#     type=click.Tuple([str, float]),
#     help="Add a starting magnetization to a specific kind.",
#     metavar="<KIND MAGNITUDE>...",
# )

# SMEARING = OverridableOption(
#     "--smearing",
#     nargs=2,
#     default=(None, None),
#     type=click.Tuple([str, float]),
#     help="Add smeared occupations by specifying the type and amount of smearing.",
#     metavar="<TYPE DEGAUSS>",
# )

VC_RELAX = OverridableOption(
    "--vc-relax",
    help="Whether to run relax in `vc-relax` mode, or in `relax` mode.",
    is_flag=True,
    default=False,
)

PH_EPSIL = OverridableOption(
    "--epsil",
    is_flag=True,
    help="whether to set calculation mode of the first qpoint to epsil.",
    default=False,
)

Q2R_ZASR = OverridableOption(  # q2r parameters
    "--q2r-zasr",
    type=click.Choice(["crystal", "no", "simple", "one-dim", "zero-dim"]),
    help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
    default="crystal",
    show_default=True,
)

MATDYN_ASR = OverridableOption(  # matdyn parameters
    "--matdyn-asr",
    type=click.Choice(["crystal", "no", "simple", "one-dim", "zero-dim"]),
    help="default is `crystal`, optionals are `no`, `simple`, `one-dim`, `zero-dim`",
    default="crystal",
    show_default=True,
)
MATDYN_DISTANCE = OverridableOption(  # matdyn parameters
    "--matdyn-distance",
    type=click.FLOAT,
    default=None,
    help="kpoint distance to get kpoints, default is kpoints_distance_for_bands in protocol.",
)

PARAMETERS = OverridableOption(
    "--parameters",
    "-p",
    multiple=True,
    callback=StoreKeyPairParam,
    help="Override parameters in protocol by specifying the key and value of parameter. e.g. ecutwfc=80...",
    metavar="key1=value1...",
)
PROTOCOL = OverridableOption(
    "--protocol",
    help="Available protocols like 'theos-ht-1.0', 'ms-1.0', and 'testing'.",
    default="ms-1.0",
    show_default=True,
)
PARAMETERS_SET = OverridableOption(
    "--parameters-set",
    help="available scf parameters sets of protocols like {`fast`, `default` and `accurate`}_{``, `fixed`, `gaussian`}",
    default="default",
    show_default=True,
)
PSEUDO_FAMILY = OverridableOption("--pseudo-family", help="pseudo family name")
CUTOFFS = OverridableOption(
    "--cutoffs",
    type=float,
    nargs=2,
    help="should be [ecutwfc] [dual]. [ecutrho] will get by dual * ecutwfc",
    default=None,
)
SYSTEM_2D = OverridableOption(
    "--system-2d",
    is_flag=True,
    help="Set mesh to 2D mesh according to cell lengths",
    default=False,
)
RUN_RELAX = OverridableOption(
    "--run-relax",
    is_flag=True,
    help="Whether to run relax before scf.",
    default=False,
)
SOC = OverridableOption(
    "--soc",
    is_flag=True,
    help="spin_orbit_coupling",
    default=False,
)
USE_PRIMITIVE_STRUCTURE = OverridableOption(
    "--use-primitive-structure",
    is_flag=True,
    help="Whether to use primitive structure.",
    default=False,
)
GROUP_NAME = OverridableOption(
    "--group-name",
    type=str,
    help="Add this task to Group",
    default=None,
)
COMPUTER = OverridableOption("-c", "--computer", type=str, help="Comptuer name")
