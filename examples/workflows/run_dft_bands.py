#!/usr/bin/env runaiida
import argparse
from aiida import orm
from aiida.engine import submit, run_get_node
from ase.io import read as aseread
from aiida_wannier90_workflows.workflows.pw.band_structure import PwBandStructureWorkChain
from aiida_wannier90_workflows.workflows.wannier.bands import Wannier90BandsWorkChain

# Please modify these according to your machine
code_str = 'qe-6.5-pw'
# code = orm.Code.get_from_string(code_str)
code = None


def read_structure(xsf_file):
    structure = orm.StructureData(ase=aseread(xsf_file))
    structure.store()
    print(
        'Structure {} read and stored with pk {}.'.format(
            structure.get_formula(), structure.pk
        )
    )
    return structure


def parse_argugments():
    parser = argparse.ArgumentParser(
        "A script to run the DFT band structure (without structural relax) using Quantum ESPRESSO starting from an automated workflow (to reuse structure), or from XSF file."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-x", "--xsf", help="path to an input XSF file")
    group.add_argument("-w", "--workchain", help="The PK of the Wannier90BandsWorkChain - if you didn't run it, run it first using the ./run_automated_wannier.py script"
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
        "-N",
        "--num_machines",
        type=int,
        help="number of machines",
        default=1
    )
    parser.add_argument("-P", "--num_mpiprocs_per_machine",
                        type=int, help="number of mpiprocs per machine", default=4)
    parser.add_argument("-C", "--computer", type=str, default='qe')
    parser.add_argument("-D", "--daemon", default=False, action='store_true')
    parser.add_argument(
        "--set_2d_mesh",
        default=False,
        action='store_true',
        help="Set mesh to [x, x, 1]",
    )
    args = parser.parse_args()
    if args.xsf is not None:
        structure = read_structure(args.xsf)
    else:
        wannier90_workchain_pk = int(args.workchain)
        try:
            wannier90_workchain = orm.load_node(wannier90_workchain_pk)
        except Exception:
            print(
                "I could not load an AiiDA node with PK={}, did you use the correct PK?"
                .format(wannier90_workchain))
            exit()
        if wannier90_workchain.process_class != Wannier90BandsWorkChain:
            print(
                "The node with PK={} is not a Wannier90BandsWorkChain, it is a {}"
                .format(wannier90_workchain_pk, type(wannier90_workchain)))
            print(
                "Please pass a node that was the output of the Wannier90 workflow executed using"
            )
            print("the ./run_automated_wannier.py script.")
            exit()
        structure = wannier90_workchain.inputs.structure
    return structure, args


def submit_workchain(structure, daemon, protocol, parameters, pseudo_family, num_machines, num_mpiprocs_per_machine=4, set_2d_mesh=False):
    print("running dft band structure calculation for {}".format(
        structure.get_formula()))

    # Set custom pseudo
    modifiers = {
        'parameters': parameters
    }
    """ if pseudo_family is not None:
        from aiida_quantumespresso.utils.protocols.pw import _load_pseudo_metadata
        pseudo_data = _load_pseudo_metadata(pseudo_family)
        modifiers.update({'pseudo': 'custom', 'pseudo_data': pseudo_data}) """
    # if pseudo_family is not None:
    #     from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_structure
    #     pseudo_data = get_pseudos_from_structure(structure, pseudo_family)
    #     modifiers.update({'pseudo': 'custom', 'pseudo_data': pseudo_data})

    # Submit the DFT bands workchain
    pwbands_workchain_parameters = {
        'code': code,
        'structure': structure,
        'protocol': orm.Dict(dict={'name': protocol, 'modifiers': modifiers}),
        'options': orm.Dict(dict={
            'resources': {
                'num_machines': num_machines,
                'num_mpiprocs_per_machine': num_mpiprocs_per_machine
            },
            'max_wallclock_seconds': 3600*5,
            'withmpi': True,
        }),
        'set_2d_mesh': orm.Bool(set_2d_mesh)
    }
    if pseudo_family is not None:
        pwbands_workchain_parameters['pseudo_family'] = orm.Str(pseudo_family)
    if daemon:
        dft_workchain = submit(
            PwBandStructureWorkChain,
            **pwbands_workchain_parameters
        )
    else:
        from aiida.engine import run_get_pk
        dft_workchain = run_get_pk(
            PwBandStructureWorkChain,
            **pwbands_workchain_parameters
        )
    return dft_workchain


def print_help(workchain, structure):
    print(
        'launched PwBandStructureWorkChain pk {} for structure {}'.format(
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

    with open('{}/{}.dft'.format(dir, workchain.pk), 'w') as f:
        f.write('verdi process report {}'.format(workchain.pk))


if __name__ == "__main__":
    structure, args = parse_argugments()
    code_str += '@{}'.format(args.computer)
    code = orm.Code.get_from_string(code_str)
    workchain = submit_workchain(
        structure, args.daemon, args.protocol, args.parameters, args.pseudo_family, args.num_machines, args.num_mpiprocs_per_machine, args.set_2d_mesh)
    print_help(workchain, structure)
