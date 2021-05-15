# -*- coding: utf-8 -*-
"""Workchain to run a Quantum ESPRESSO ph.x calculation with automated error handling and restarts."""
from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import (
    while_,
    process_handler,
    ProcessHandlerReport,
)
from aiida_mobility.workflows import BaseRestartWorkChain
from aiida.plugins import CalculationFactory

PhCalculation = CalculationFactory("quantumespresso.ph")
PwCalculation = CalculationFactory("quantumespresso.pw")


class PhBaseWorkChain(BaseRestartWorkChain):
    """Workchain to run a Quantum ESPRESSO ph.x calculation with automated error handling and restarts."""

    _process_class = PhCalculation

    defaults = AttributeDict(
        {
            "delta_factor_max_seconds": 0.95,
            "delta_factor_alpha_mix": 0.90,
            "alpha_mix": 0.70,
        }
    )

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        # yapf: disable
        super().define(spec)
        spec.expose_inputs(PhCalculation, namespace='ph')
        spec.input('check_imaginary_frequencies', valid_type=orm.Bool,default=lambda: orm.Bool(True), help='whether to check imaginary frequencies.')
        spec.input('frequency_threshold', valid_type=orm.Float, default=lambda: orm.Float(-15.0), help='The threshold to check if imaginary frequencies exsit in G.')
        spec.input('separated_qpoints', valid_type=orm.Bool,default=lambda: orm.Bool(False), help='Set true if you want to calculate each qpoint separately.')
        spec.input('parent_scf_node_mode', valid_type=orm.Bool, default=lambda: orm.Bool(False), help='The calculation mode of parent node: scf or ph.')
        spec.input('only_initialization', valid_type=orm.Bool,
                   default=lambda: orm.Bool(False))

        spec.outline(
            cls.setup,
            cls.validate_parameters,
            cls.validate_resources,
            while_(cls.should_run_process)(
                cls.prepare_process,
                cls.run_process,
                cls.inspect_process,
            ),
            cls.results,
        )
        spec.expose_outputs(PwCalculation, exclude=('retrieved_folder',))
        spec.exit_code(204, 'ERROR_INVALID_INPUT_RESOURCES_UNDERSPECIFIED',
                       message='The `metadata.options` did not specify both `resources.num_machines` and `max_wallclock_seconds`.')
        spec.exit_code(300, 'ERROR_UNRECOVERABLE_FAILURE',
                       message='The calculation failed with an unrecoverable error.')
        spec.exit_code(301, 'ERROR_IMAGINARY_FREQUENCIES',
                       message='The calculation failed with an imaginary frequencies error.')

        # yapf: enable

    def setup(self):
        """Call the `setup` of the `BaseRestartWorkChain` and then create the inputs dictionary in `self.ctx.inputs`.

        This `self.ctx.inputs` dictionary will be used by the `BaseRestartWorkChain` to submit the calculations in the
        internal loop.
        """
        super().setup()
        self.ctx.restart_calc = None
        self.ctx.check_imaginary_frequencies = (
            self.inputs.check_imaginary_frequencies.value
        )
        self.ctx.frequency_threshold = self.inputs.frequency_threshold.value
        self.ctx.inputs = AttributeDict(
            self.exposed_inputs(PhCalculation, "ph")
        )

    def validate_parameters(self):
        """Validate inputs that might depend on each other and cannot be validated by the spec."""
        self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
        self.ctx.inputs.settings = (
            self.ctx.inputs.settings.get_dict()
            if "settings" in self.ctx.inputs
            else {}
        )

        self.ctx.inputs.parameters.setdefault("INPUTPH", {})
        self.ctx.inputs.parameters["INPUTPH"]["recover"] = (
            "parent_folder" in self.ctx.inputs
        )

        if self.inputs.only_initialization.value:
            self.ctx.inputs.settings["ONLY_INITIALIZATION"] = True

        self.ctx.current_qpoint = self.ctx.inputs.parameters["INPUTPH"].get(
            "start_q", 1
        )
        self.ctx.max_qpoint = self.ctx.inputs.parameters["INPUTPH"].get(
            "last_q", max(self.ctx.inputs.qpoints.get_attribute("mesh"))
        )
        # if self.inputs.separated_qpoints.value:
        self.ctx.inputs.parameters["INPUTPH"][
            "start_q"
        ] = self.ctx.current_qpoint
        self.ctx.inputs.parameters["INPUTPH"][
            "last_q"
        ] = self.ctx.current_qpoint

    def validate_resources(self):
        """Validate the inputs related to the resources.

        The `metadata.options` should at least contain the options `resources` and `max_wallclock_seconds`, where
        `resources` should define the `num_machines`.
        """
        num_machines = self.ctx.inputs.metadata.options.get(
            "resources", {}
        ).get("num_machines", None)
        max_wallclock_seconds = self.ctx.inputs.metadata.options.get(
            "max_wallclock_seconds", None
        )

        if num_machines is None or max_wallclock_seconds is None:
            return self.exit_codes.ERROR_INVALID_INPUT_RESOURCES_UNDERSPECIFIED

        self.set_max_seconds(max_wallclock_seconds)

    def set_max_seconds(self, max_wallclock_seconds):
        """Set the `max_seconds` to a fraction of `max_wallclock_seconds` option to prevent out-of-walltime problems.

        :param max_wallclock_seconds: the maximum wallclock time that will be set in the scheduler settings.
        """
        max_seconds_factor = self.defaults.delta_factor_max_seconds
        max_seconds = max_wallclock_seconds * max_seconds_factor
        self.ctx.inputs.parameters["INPUTPH"]["max_seconds"] = max_seconds

    def prepare_process(self):
        """Prepare the inputs for the next calculation.

        If a `restart_calc` has been set in the context, its `remote_folder` will be used as the `parent_folder` input
        for the next calculation and the `restart_mode` is set to `restart`.
        """
        if self.ctx.restart_calc:
            if "no_recover" in self.ctx and self.ctx.no_recover:
                self.ctx.inputs.parameters["INPUTPH"]["recover"] = False
            else:
                self.ctx.inputs.parameters["INPUTPH"]["recover"] = True
            self.ctx.inputs.parent_folder = (
                self.ctx.restart_calc.outputs.remote_folder
            )

    def report_error_handled(self, calculation, action):
        """Report an action taken for a calculation that has failed.

        This should be called in a registered error handler if its condition is met and an action was taken.

        :param calculation: the failed calculation node
        :param action: a string message with the action taken
        """
        arguments = [
            calculation.process_label,
            calculation.pk,
            calculation.exit_status,
            calculation.exit_message,
        ]
        self.report("{}<{}> failed with exit status {}: {}".format(*arguments))
        self.report(f"Action taken: {action}")

    @process_handler(priority=600)
    def handle_unrecoverable_failure(self, node):
        """Handle calculations with an exit status below 400 which are unrecoverable, so abort the work chain."""
        if node.is_failed and node.exit_status < 400:
            self.report_error_handled(node, "unrecoverable error, aborting...")
            return ProcessHandlerReport(
                True, self.exit_codes.ERROR_UNRECOVERABLE_FAILURE
            )

    @process_handler(priority=590)
    def handle_imaginary_frequencies(self, node):
        """Handle calculations with imaginary frequencies in dynamical_matrix_1.
        Currently checking the first point only, adding a counter to check more. Not availble to a recover calculation."""
        # for value in $(seq 2 1 14)
        #     do
        #     cp ph.in ph_$value.in
        #     sed -i  "s|.*start_q.*|    start_q = $value |g" ph_$value.in
        #     sed -i  "s|.*last_q.*|    last_q = $value |g" ph_$value.in
        #     mpirun -n 72 ph.x < ph_$value.in > ph_$value.out
        # done
        def start_next(action, separated=False):
            if self.ctx.current_qpoint >= self.ctx.max_qpoint or (
                self.inputs.separated_qpoints.value is False
                and self.ctx.current_qpoint > 1
            ):
                self.ctx.is_finished = True
                return
            self.ctx.restart_calc = node
            # self.ctx.no_recover = False
            if (
                "epsil" in self.ctx.inputs.parameters["INPUTPH"]
                and self.ctx.inputs.parameters["INPUTPH"]["epsil"] == True
            ):
                self.ctx.inputs.parameters["INPUTPH"]["epsil"] = False
                self.ctx.no_recover = True

            if separated is True:
                self.ctx.inputs.settings["PARENT_FOLDER_SYMLINK"] = True
                self.ctx.current_qpoint += 1
                self.ctx.inputs.parameters["INPUTPH"][
                    "start_q"
                ] = self.ctx.current_qpoint
                self.ctx.inputs.parameters["INPUTPH"][
                    "last_q"
                ] = self.ctx.current_qpoint
            else:
                self.ctx.current_qpoint += 1
                self.ctx.inputs.parameters["INPUTPH"][
                    "start_q"
                ] = self.ctx.current_qpoint
                self.ctx.inputs.parameters["INPUTPH"][
                    "last_q"
                ] = self.ctx.max_qpoint

            self.report_error_handled(node, action)

        if node.is_finished_ok and (
            "parent_folder" not in self.inputs
            or self.inputs.parent_scf_node_mode.value
        ):
            # TODO: whether or not to check every point?
            number_of_qpoints = node.outputs.output_parameters.get_dict().get(
                "number_of_qpoints", None
            )
            if (
                number_of_qpoints is not None
                and self.ctx.max_qpoint != number_of_qpoints
            ):
                self.ctx.max_qpoint = number_of_qpoints
                # separate calculation times do not need to add to iteration_times
                if self.inputs.separated_qpoints.value:
                    self.ctx.max_iterations += 2 * self.ctx.max_qpoint
                else:
                    self.ctx.max_iterations += 2
            if self.ctx.check_imaginary_frequencies:
                matrix_name = "dynamical_matrix_{}".format(
                    self.ctx.current_qpoint
                )
                self.report_error_handled(
                    node,
                    "checking imaginary frequencies in {}...".format(
                        matrix_name
                    ),
                )
                try:
                    dynamical_matrix = (
                        node.outputs.output_parameters.get_dict().get(
                            matrix_name, None
                        )
                    )
                    frequencies = dynamical_matrix.get("frequencies", None)
                    if frequencies is None:
                        raise AttributeError("frequencies is None.")
                    else:
                        if frequencies[0] > self.ctx.frequency_threshold:
                            start_next(
                                action="checked point {} successfuly and just restarting to next one...".format(
                                    self.ctx.current_qpoint
                                ),
                                separated=self.inputs.separated_qpoints.value,
                            )
                            return ProcessHandlerReport(True)
                        else:
                            self.report_error_handled(
                                node,
                                "imaginary frequencies found at point {}, aborting...".format(
                                    self.ctx.current_qpoint
                                ),
                            )
                            return ProcessHandlerReport(
                                True,
                                self.exit_codes.ERROR_IMAGINARY_FREQUENCIES,
                            )
                except AttributeError as err:
                    self.report_error_handled(
                        node,
                        "[{}]. Not found valid dynamical_matrix_{} outputs, restarting...".format(
                            err, self.ctx.current_qpoint
                        ),
                    )
                    return ProcessHandlerReport(True)
            else:
                start_next(
                    action="Not check point {} and just restarting to next one...".format(
                        self.ctx.current_qpoint
                    ),
                    separated=self.inputs.separated_qpoints.value,
                )
                return ProcessHandlerReport(True)

    @process_handler(
        priority=580, exit_codes=PhCalculation.exit_codes.ERROR_OUT_OF_WALLTIME
    )
    def handle_out_of_walltime(self, node):
        """Handle `ERROR_OUT_OF_WALLTIME` exit code: calculation shut down neatly and we can simply restart."""
        self.ctx.restart_calc = node
        self.report_error_handled(
            node, "simply restart from the last calculation"
        )
        return ProcessHandlerReport(True)

    @process_handler(
        priority=410,
        exit_codes=PhCalculation.exit_codes.ERROR_CONVERGENCE_NOT_REACHED,
    )
    def handle_convergence_not_achieved(self, node):
        """Handle `ERROR_CONVERGENCE_NOT_REACHED` exit code: decrease the mixing beta and restart from scratch."""
        factor = self.defaults.delta_factor_alpha_mix
        alpha_mix = self.ctx.inputs.parameters.get("INPUTPH", {}).get(
            "alpha_mix(1)", self.defaults.alpha_mix
        )
        alpha_mix_new = alpha_mix * factor

        self.ctx.restart_calc = node
        self.ctx.inputs.parameters.setdefault("INPUTPH", {})[
            "alpha_mix(1)"
        ] = alpha_mix_new

        action = f"reduced alpha_mix from {alpha_mix} to {alpha_mix_new} and restarting"
        self.report_error_handled(node, action)
        return ProcessHandlerReport(True)
