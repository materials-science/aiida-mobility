from aiida.common.extendeddicts import AttributeDict
from aiida.engine.processes.workchains.context import ToContext
from aiida_mobility.workflows.wannier.bands import Wannier90BandsWorkChain
from aiida_mobility.workflows.ph.bands import (
    PhBandsWorkChain,
)
from aiida.engine.processes.workchains.workchain import WorkChain
from aiida import orm


def validate_inputs(inputs, ctx=None):  # pylint: disable=unused-argument
    pass


class PertuborWorkChain(WorkChain):
    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input(
            "structure",
            valid_type=orm.StructureData,
            help="The inputs structure.",
        )
        spec.expose_inputs(
            PhBandsWorkChain,
            namespace="ph",
            exclude=("structure", "clean_workdir", "dry_run"),
        )
        spec.expose_inputs(
            Wannier90BandsWorkChain,
            namespace="wannier",
            exclude=("structure", "clean_workdir", "dry_run"),
        )
        spec.input(
            "system_2d",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="Set the mesh to [x,x,1]",
        )
        spec.input(
            "clean_workdir",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="If `True`, work directories of all called calculation will be cleaned at the end of execution.",
        )
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.setup,
            cls.run_ph_bands,
            cls.run_automated_wannier,
            cls.run_qe2pert,
            cls.run_pert,
            cls.results,
        )
        spec.exit_code(
            300,
            "ERROR_INVALID_SCF_NODE",
            message="The scf node is invalid or does not have remote folder",
        )

    def run_ph_bands(self):
        inputs = AttributeDict(
            self.exposed_inputs(PhBandsWorkChain, namespace="ph")
        )
        inputs.metadata.call_link_label = "ph"
        inputs.structure = self.ctx.current_structure

        running = self.submit(PhBandsWorkChain, **inputs)

        self.report("launching PhBandsWorkChain<{}>".format(running.pk))

        return ToContext(workchain_ph=running)

    def run_automated_wannier(self):
        inputs = AttributeDict(
            self.exposed_inputs(Wannier90BandsWorkChain, namespace="ph")
        )
        inputs.metadata.call_link_label = "wannier"
        inputs.structure = self.ctx.current_structure

        running = self.submit(Wannier90BandsWorkChain, **inputs)

        self.report("launching Wannier90BandsWorkChain<{}>".format(running.pk))

        return ToContext(workchain_wannier=running)