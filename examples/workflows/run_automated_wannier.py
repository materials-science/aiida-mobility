#!/usr/bin/env runaiida
import argparse
from aiida import orm
from aiida.engine import submit
from aiida.common.exceptions import NotExistent
from aiida.engine.processes.workchains import workchain
from ase.io import read as aseread
from aiida_wannier90_workflows.workflows import Wannier90BandsWorkChain

# Please modify these according to your machine
str_pw = 'qe-6.5-pw'
str_pw2wan = 'pw2wannier90'
str_projwfc = 'projwfc'
str_wan = 'wannier-3.0'

group_name = 'scdm_workflow'


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
            'Please modify the code labels in this script according to your machine'
        )
        exit(1)
    return codes


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to run the AiiDA workflows to automatically compute the MLWF using the SCDM method and the automated protocol described in the Vitale et al. paper"
    )
    parser.add_argument(
        '-S',
        '--structure', metavar="FILENAME", help="path to an input Structure(xsf,cif,poscar) file"
    )
    parser.add_argument(
        "-p",
        "--parameters",
        help="available parameters protocols are 'fast', 'default' and 'accurate'",
        default="default"
    )
    parser.add_argument(
        "--protocol",
        help="available protocols are 'theos-ht-1.0' and 'testing'",
        default="theos-ht-1.0"
    )
    parser.add_argument(
        "--pseudo-family",
        help="pseudo family name",
        default=None
    )
    parser.add_argument(
        '-m',
        "--do-mlwf",
        help="do maximal localization of Wannier functions",
        action="store_false"
    )
    parser.add_argument(
        '-d',
        "--do-disentanglement",
        help="do disentanglement in Wanner90 step (This should be False, otherwise band structure is not optimal!)",
        action="store_true"
    )
    parser.add_argument(
        '-v',
        "--only-valence",
        help="Compute only for valence bands (you must be careful to apply this only for insulators!)",
        action="store_true"
    )
    parser.add_argument(
        '-r',
        "--retrieve-hamiltonian",
        help="Retrieve Wannier Hamiltonian after the workflow finished",
        action="store_true"
    )
    parser.add_argument(
        "-N",
        "--num_machines",
        type=int,
        help="number of machines",
        default=1
    )
    parser.add_argument(
        "-P",
        "--num_mpiprocs_per_machine",
        type=int,
        help="number of mpiprocs per machine",
        default=8
    )
    parser.add_argument(
        '-C',
        "--computer",
        type=str,
        default='qe'
    )
    parser.add_argument(
        "--set_2d_mesh",
        default=False,
        action='store_true',
        help="Set mesh to [x, x, 1]",
    )
    parser.add_argument(
        "-D",
        "--daemon",
        default=False,
        action='store_true',
        help="Run with submit",
    )
    parser.add_argument(
        "--group_name",
        type=str,
        help="Add this task to Group",
        default='scdm_workflow'
    )
    args = parser.parse_args()
    return args


def read_structure(structure_file):
    structure = orm.StructureData(ase=aseread(structure_file))
    structure.store()
    print(
        'Structure {} read and stored with pk {}.'.format(
            structure.get_formula(), structure.pk
        )
    )
    return structure


def update_group_name(group_name, only_valence, do_disen, do_mlwf, exclude_bands=None):
    if only_valence:
        group_name += "_onlyvalence"
    else:
        group_name += "_withconduction"
    if do_disen:
        group_name += '_disentangle'
    if do_mlwf:
        group_name += '_mlwf'
    if exclude_bands is not None:
        group_name += '_excluded{}'.format(len(exclude_bands))
    return group_name


def add_to_group(node, group_name):
    if group_name is not None:
        try:
            g = orm.Group.get(label=group_name)
            group_statistics = "that already contains {} nodes".format(
                len(g.nodes)
            )
        except NotExistent:
            g = orm.Group(label=group_name)
            group_statistics = "that does not exist yet"
            g.store()
        g.add_nodes(node)
        print(
            "Wannier90BandsWorkChain<{}> will be added to the group {} {}".
            format(node.pk, group_name, group_statistics)
        )


def print_help(workchain, structure):
    print(
        'launched Wannier90BandsWorkChain pk {} for structure {}'.format(
            workchain.pk, structure.get_formula()
        )
    )
    print('')
    print('# To get a detailed state of the workflow, run:')
    print('verdi process report {}'.format(workchain.pk))
    import os
    dir = '{}'.format(structure.get_formula())
    if not os.path.isdir(dir):
        os.mkdir(dir)

    with open('{}/{}.wannier'.format(dir, workchain.pk), 'w') as f:
        f.write('verdi process report {}'.format(workchain.pk))


def submit_workchain(structure_file, num_machines, num_mpiprocs_per_machine, protocol, parameters, pseudo_family, only_valence, do_disentanglement, do_mlwf, retrieve_hamiltonian, group_name, daemon, set_2d_mesh):
    codes = check_codes()

    group_name = update_group_name(
        group_name, only_valence, do_disentanglement, do_mlwf
    )

    if isinstance(structure_file, orm.StructureData):
        structure = structure_file
    else:
        structure = read_structure(structure_file)

    controls = {
        'retrieve_hamiltonian': orm.Bool(retrieve_hamiltonian),
        'only_valence': orm.Bool(only_valence),
        'do_disentanglement': orm.Bool(do_disentanglement),
        'do_mlwf': orm.Bool(do_mlwf)
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

    modifiers = {
        'parameters': parameters
    }
    # if pseudo_family is not None:
    # from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_structure
    # pseudo_data = get_pseudos_from_structure(structure, pseudo_family)
    # modifiers.update({'pseudo': pseudo_family})

    wannier90_workchain_parameters = {
        "code": {
            'pw': codes['pw_code'],
            'pw2wannier90': codes['pw2wannier90_code'],
            'projwfc': codes['projwfc_code'],
            'wannier90': codes['wannier90_code']
        },
        "protocol": orm.Dict(dict={'name': protocol, 'modifiers': modifiers}),
        "structure": structure,
        "controls": controls,
        "options": orm.Dict(dict={
            'resources': {
                'num_machines': num_machines,
                'num_mpiprocs_per_machine': num_mpiprocs_per_machine
            },
            'max_wallclock_seconds': 3600 * 5,
            'withmpi': True
        }),
        'set_2d_mesh': orm.Bool(set_2d_mesh),
    }

    if pseudo_family is not None:
        wannier90_workchain_parameters['pseudo_family'] = orm.Str(
            pseudo_family)

    if daemon is not None:
        workchain = submit(
            Wannier90BandsWorkChain, **wannier90_workchain_parameters
        )
    else:
        from aiida.engine import run_get_pk
        from aiida.orm import load_node
        workchain = run_get_pk(Wannier90BandsWorkChain,
                               **wannier90_workchain_parameters)

    add_to_group(workchain, group_name)
    print_help(workchain, structure)
    return workchain.pk


if __name__ == "__main__":
    args = parse_arugments()
    str_pw += '@{}'.format(args.computer)
    str_pw2wan += '@{}'.format(args.computer)
    str_projwfc += '@{}'.format(args.computer)
    str_wan += '@{}'.format(args.computer)
    submit_workchain(
        args.structure, args.num_machines, args.num_mpiprocs_per_machine, args.protocol, args.parameters, args.pseudo_family, args.only_valence, args.do_disentanglement,
        args.do_mlwf, args.retrieve_hamiltonian, args.group_name, args.daemon, args.set_2d_mesh
    )
