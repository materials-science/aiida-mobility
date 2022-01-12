"""
aiida_mobility

aiida plugin for mobility calculations
"""

__version__ = "0.1.0a0"

from aiida.engine import CalcJob
from aiida.orm import Bool


class BaseCalculation(CalcJob):
    """
    A basic calculation.
    """

    _OUTPUT_SUBFOLDER = ""
    _PREFIX = "aiida"
    _DEFAULT_INPUT_FILE = "aiida.in"
    _DEFAULT_OUTPUT_FILE = "aiida.out"

    _DEFAULT_METADATA_RESOURCES = {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 1,
    }

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input(
            "metadata.options.resources",
            valid_type=dict,
            default=cls._DEFAULT_METADATA_RESOURCES,
            help="resources designated for calculation.",
        )
        spec.input(
            "metadata.options.withmpi",
            valid_type=bool,
            default=False,
            help="Run with mpi.",
        )
        spec.input(
            "metadata.dry_run",
            valid_type=bool,
            required=False,
            default=False,
            non_db=True,
            help="Dry run without submission for test",
        )
        spec.input(
            "metadata.store_provenance",
            valid_type=bool,
            required=False,
            default=True,
            non_db=True,
            help="Set False to unable creating nodes",
        )
        spec.input(
            "clean_workdir",
            valid_type=Bool,
            required=False,
            default=lambda: Bool(False),
            help="""If True, clean the work dir upon the completion of a successfull calculation.""",
        )

    def on_terminated(self):
        """Clean remote folders of the calculations called in the workchain if the clean_workdir input is True."""

        super().on_terminated()  # pylint: disable=no-member
        # Do not clean if we do not want to or the calculation failed
        if self.node.exit_status or self.inputs.clean_workdir.value is False:
            self.report(
                "not cleaning the remote folders"
            )  # pylint: disable=not-callable
            return

        cleaned_calcs = []
        try:
            self.outputs["remote_folder"]._clean()
            cleaned_calcs.append(self.node.pk)
        except BaseException:
            pass
        if cleaned_calcs:
            self.report(
                "cleaned remote folders of calculations: {}".format(
                    " ".join(map(str, cleaned_calcs))
                )
            )  # pylint: disable=not-callable
