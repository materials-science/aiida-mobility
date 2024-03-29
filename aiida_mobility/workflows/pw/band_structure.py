# -*- coding: utf-8 -*-
"""Workchain to automatically compute a band structure for a given structure using Quantum ESPRESSO pw.x.
This is a copy of the one included in aiida_quantumespresso, the diff is that this one does not do relax calculation."""
from aiida_mobility.utils import input_pw_parameters_helper
from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import WorkChain, ToContext
from aiida.orm.nodes.data.upf import get_pseudos_from_structure
from aiida.plugins import WorkflowFactory

from aiida_mobility.utils.protocols.pw import ProtocolManager
from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_dict
from aiida_quantumespresso.utils.resources import get_default_options

from aiida_mobility.workflows.pw.bands import PwBandsWorkChain
# PwBandsWorkChain = WorkflowFactory('quantumespresso.pw.bands')


def validate_protocol(protocol_dict):
    """Check that the protocol is one for which we have a definition."""
    try:
        protocol_name = protocol_dict['name']
    except KeyError as exception:
        return 'Missing key `name` in protocol dictionary'
    try:
        ProtocolManager(protocol_name)
    except ValueError as exception:
        return str(exception)


def validate_cutoffs(cutoffs_dict, ctx):
    try:
        cutoff = cutoffs_dict['cutoff']
        dual = cutoffs_dict['dual']
    except KeyError as exception:
        return 'Missing key `cutoff` or `dual` in cutoffs dictionary'
    except TypeError:
        pass


class PwBandStructureWorkChain(WorkChain):
    """Workchain to automatically compute a band structure for a given structure using Quantum ESPRESSO pw.x."""
    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        # yapf: disable
        super(PwBandStructureWorkChain, cls).define(spec)
        spec.input('code', valid_type=orm.Code,
                   help='The `pw.x` code to use for the `PwCalculations`.')
        spec.input('structure', valid_type=orm.StructureData,
                   help='The input structure.')
        spec.input('options', valid_type=orm.Dict, required=False,
                   help='Optional `options` to use for the `PwCalculations`.')
        spec.input('protocol', valid_type=orm.Dict, default=lambda: orm.Dict(dict={'name': 'theos-ht-1.0'}),
                   help='The protocol to use for the workchain.', validator=validate_protocol)
        # MODIFIED
        spec.input('pseudo_family', valid_type=orm.Str, required=False,
                   help='[Deprecated: use `pw.pseudos` instead] An alternative to specifying the pseudo potentials manually in'
                   ' `pseudos`: one can specify the name of an existing pseudo potential family and the work chain will '
                   'generate the pseudos automatically based on the input structure.')
        spec.input('system_2d', valid_type=orm.Bool, default=lambda: orm.Bool(
            False), help='Set the mesh to [x,x,1]')
        spec.input(
            'cutoffs',
            valid_type=orm.Dict,
            required=False,
            help='Recommended cutoffs. e.g. {"cutoff": 30, "dual": 4.9}',
            validator=validate_cutoffs
        )
        spec.input(
            "kpoints",
            valid_type=orm.KpointsData,
            required=False,
            help="An explicit k-points list or mesh. Either this or `kpoints_distance` has to be provided.",
        )
        spec.input(
            'should_run_relax',
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help='Whether to run relax before scf.',
        )
        spec.expose_outputs(PwBandsWorkChain)
        spec.outline(
            cls.setup_protocol,
            cls.setup_parameters,
            cls.run_bands,
            cls.results,
        )
        spec.exit_code(201, 'ERROR_INVALID_INPUT_UNRECOGNIZED_KIND',
                       message='Input `StructureData` contains an unsupported kind.')
        spec.exit_code(401, 'ERROR_SUB_PROCESS_FAILED_BANDS',
                       message='The `PwBandsWorkChain` sub process failed.')
        spec.output('primitive_structure', valid_type=orm.StructureData)
        spec.output('seekpath_parameters', valid_type=orm.Dict)
        spec.output('scf_parameters', valid_type=orm.Dict)
        spec.output('band_parameters', valid_type=orm.Dict)
        spec.output('band_structure', valid_type=orm.BandsData)

    def _get_protocol(self):
        """Return a `ProtocolManager` instance and a dictionary of modifiers."""
        protocol_data = self.inputs.protocol.get_dict()
        protocol_name = protocol_data['name']
        protocol = ProtocolManager(protocol_name)

        protocol_modifiers = protocol_data.get('modifiers', {})

        return protocol, protocol_modifiers

    def setup_protocol(self):
        """Set up context variables and inputs for the `PwBandsWorkChain`.

        Based on the specified protocol, we define values for variables that affect the execution of the calculations.
        """
        protocol, protocol_modifiers = self._get_protocol()
        self.report(
            'running the workchain with the "{}" protocol'.format(protocol.name))
        self.ctx.protocol = protocol.get_protocol_data(
            modifiers=protocol_modifiers)

    def setup_parameters(self):
        """Set up the default input parameters required for the `PwBandsWorkChain`."""
        ecutwfc = []
        ecutrho = []

        if 'cutoffs' in self.inputs:
            cutoff = self.inputs.cutoffs['cutoff']
            dual = self.inputs.cutoffs['dual']
            ecutwfc.append(cutoff)
            ecutrho.append(dual * cutoff)
        else:
            for kind in self.inputs.structure.get_kind_names():
                try:
                    dual = self.ctx.protocol['pseudo_data'][kind]['dual']
                    cutoff = self.ctx.protocol['pseudo_data'][kind]['cutoff']
                    cutrho = dual * cutoff
                    ecutwfc.append(cutoff)
                    ecutrho.append(cutrho)
                except KeyError:
                    self.report(
                        'failed to retrieve the cutoff or dual factor for {}'.format(kind))
                    return self.exit_codes.ERROR_INVALID_INPUT_UNRECOGNIZED_KIND

        prepare_for_parameters = self.ctx.protocol
        prepare_for_parameters.update({
            'CONTROL': {
                'restart_mode': 'from_scratch',
                'tstress': self.ctx.protocol['tstress'],
                'tprnfor': self.ctx.protocol['tprnfor'],
            },
            'SYSTEM': {
                'ecutwfc': max(ecutwfc),
                'ecutrho': max(ecutrho),
                # 'smearing': self.ctx.protocol['smearing'],
                # 'degauss': self.ctx.protocol['degauss'],
                # 'occupations': self.ctx.protocol['occupations'],
            },
            'ELECTRONS': {
                'conv_thr': self.ctx.protocol['convergence_threshold_per_atom'] * len(self.inputs.structure.sites),
            }
        })
        # if 'smearing' in self.ctx.protocol:
        #     parameters['SYSTEM']['smearing'] = self.ctx.protocol['smearing']
        # if 'degauss' in self.ctx.protocol:
        #     parameters['SYSTEM']['degauss'] = self.ctx.protocol['degauss']
        # if 'occupations' in self.ctx.protocol:
        #     parameters['SYSTEM']['occupations'] = self.ctx.protocol['occupations']
        parameters = input_pw_parameters_helper(
            "scf", prepare_for_parameters
        )

        self.ctx.parameters = orm.Dict(dict=parameters)

    def run_bands(self):
        """Run the `PwBandsWorkChain` to compute the band structure."""
        def get_common_inputs():
            """Return the dictionary of inputs to be used as the basis for each `PwBaseWorkChain`."""
            protocol, protocol_modifiers = self._get_protocol()
            checked_pseudos = protocol.check_pseudos(
                modifier_name=protocol_modifiers.get('pseudo', None),
                pseudo_data=protocol_modifiers.get('pseudo_data', None))
            known_pseudos = checked_pseudos['found']

            inputs = AttributeDict({
                'pw': {
                    'code': self.inputs.code,
                    'parameters': self.ctx.parameters,
                    'metadata': {},
                }
            })

            if 'pseudo_family' in self.inputs:
                inputs.pw['pseudos'] = get_pseudos_from_structure(
                    self.inputs.structure, self.inputs.pseudo_family.value)
            else:
                inputs.pw['pseudos'] = get_pseudos_from_dict(
                    self.inputs.structure, known_pseudos)

            if 'system_2d' in self.inputs:
                inputs['system_2d'] = self.inputs.system_2d

            if 'options' in self.inputs:
                inputs.pw.metadata.options = self.inputs.options.get_dict()
            else:
                inputs.pw.metadata.options = get_default_options(with_mpi=True)

            return inputs

        def get_relax_inputs():
            """get_relax_inputs Get relaxation inputs .
            """
            inputs = AttributeDict({
                'base': get_common_inputs(),
                'relaxation_scheme': orm.Str('vc-relax'),
                'meta_convergence': orm.Bool(self.ctx.protocol['meta_convergence']),
                'volume_convergence': orm.Float(self.ctx.protocol['volume_convergence']),
            })
            parameters = inputs["base"]["pw"]["parameters"].get_dict()
            parameters.setdefault("CELL", {})
            return inputs

        inputs = AttributeDict({
            'structure': self.inputs.structure,
            'scf': get_common_inputs(),
            'bands': get_common_inputs(),
        })

        if self.inputs.should_run_relax.value:
            inputs['relax'] = get_relax_inputs()
            inputs.relax.base.kpoints_distance = orm.Float(
                self.ctx.protocol['kpoints_mesh_density'])
        if "kpoints" in self.inputs:
            inputs.scf.kpoints = self.inputs.kpoints
        else:
            inputs.scf.kpoints_distance = orm.Float(
                self.ctx.protocol['kpoints_mesh_density'])
        # TODO: 2D materials
        inputs.bands.kpoints_distance = orm.Float(
            self.ctx.protocol['kpoints_distance_for_bands'])

        num_bands_factor = self.ctx.protocol.get('num_bands_factor', None)
        if num_bands_factor is not None:
            inputs.nbands_factor = orm.Float(num_bands_factor)

        running = self.submit(PwBandsWorkChain, **inputs)

        self.report('launching PwBandsWorkChain<{}>'.format(running.pk))

        return ToContext(workchain_bands=running)

    def results(self):
        """Attach the relevant output nodes from the band calculation to the workchain outputs for convenience."""
        workchain = self.ctx.workchain_bands

        if not self.ctx.workchain_bands.is_finished_ok:
            self.report(
                'sub process PwBandsWorkChain<{}> failed'.format(workchain.pk))
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_BANDS

        self.report('workchain successfully completed')
        link_labels = [
            'primitive_structure',
            'seekpath_parameters',
            'scf_parameters',
            'band_parameters',
            'band_structure'
        ]

        for link_triple in workchain.get_outgoing().all():
            if link_triple.link_label in link_labels:
                self.out(link_triple.link_label, link_triple.node)
