from aiida_mobility.utils import constr2dpath, create_kpoints
from aiida import orm
from aiida.orm import (
    Dict,
    StructureData,
    Float,
    Bool,
    CalcJobNode,
    Int,
    KpointsData,
)
from aiida.common import AttributeDict
from aiida.engine import WorkChain, ToContext, if_, while_
from aiida.orm.utils import load_node

from aiida_quantumespresso.calculations.functions.seekpath_structure_analysis import (
    seekpath_structure_analysis,
)
from aiida_quantumespresso.utils.mapping import prepare_process_inputs

from aiida_mobility.workflows.pw.base import PwBaseWorkChain
from aiida_mobility.workflows.pw.relax import PwRelaxWorkChain
from aiida_mobility.workflows.ph.base import PhBaseWorkChain
from aiida_quantumespresso.workflows.q2r.base import Q2rBaseWorkChain
from aiida_quantumespresso.workflows.matdyn.base import MatdynBaseWorkChain


def validate_inputs(inputs, ctx=None):  # pylint: disable=unused-argument
    """Validate the inputs of the entire input namespace."""
    if "scf_node" in inputs:
        try:
            scf = load_node(inputs["scf_node"].value)
            remote = scf.outputs.remote_folder
        except Exception:
            return PhBandsWorkChain.exit_codes.ERROR_INVALID_SCF_NODE.message
    if "ph_node" in inputs:
        try:
            ph = load_node(inputs["ph_node"].value)
            remote = ph.outputs.remote_folder
        except Exception:
            return PhBandsWorkChain.exit_codes.ERROR_INVALID_PH_NODE.message
    if "q2r_node" in inputs:
        try:
            q2r = load_node(inputs["q2r_node"].value)
            remote = q2r.outputs.remote_folder
        except Exception:
            return PhBandsWorkChain.exit_codes.ERROR_INVALID_Q2R_NODE.message
    if "qpoints" not in inputs and "qpoints_distance" not in inputs:
        return PhBandsWorkChain.exit_codes.ERROR_INVALID_QPOINTS.message


class PhBandsWorkChain(WorkChain):
    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.expose_inputs(
            PwRelaxWorkChain,
            namespace="relax",
            exclude=("clean_workdir", "structure"),
            namespace_options={
                "required": False,
                "populate_defaults": False,
                "help": "Inputs for the `PwRelaxWorkChain`, if not specified at all, the relaxation step is skipped.",
            },
        )
        spec.expose_inputs(
            PwBaseWorkChain,
            namespace="scf",
            exclude=("clean_workdir", "pw.structure"),
            namespace_options={
                "help": "Inputs for the `PwBaseWorkChain` for the SCF calculation."
            },
        )
        spec.expose_inputs(
            PhBaseWorkChain,
            namespace="ph",
            exclude=("ph.parent_folder", "ph.qpoints"),
        )
        spec.expose_inputs(
            Q2rBaseWorkChain, namespace="q2r", exclude=("q2r.parent_folder",)
        )
        spec.expose_inputs(
            MatdynBaseWorkChain,
            namespace="matdyn",
            exclude=("matdyn.force_constants", "matdyn.kpoints"),
        )
        spec.input(
            "structure", valid_type=StructureData, help="The inputs structure."
        )
        spec.input(
            "qpoints",
            valid_type=orm.KpointsData,
            required=False,
            help="qpoints.",
        )
        spec.input(
            "qpoints_distance",
            valid_type=Float,
            required=False,
            help="qpoint distance to get qpoints.",
        )
        spec.input(
            "matdyn_distance",
            valid_type=Float,
            required=False,
            help="matdyn kpoints distance.",
        )
        spec.input(
            "max_restart_iterations",
            valid_type=Int,
            default=lambda: Int(5),
            help="The max iterations to restart from relax.",
        )
        spec.input(
            "scf_node",
            valid_type=Int,
            required=False,
            help="The finished scf node.",
        )
        spec.input(
            "ph_node",
            valid_type=Int,
            required=False,
            help="The finished ph node.",
        )
        spec.input(
            "q2r_node",
            valid_type=Int,
            required=False,
            help="The finished q2r node.",
        )
        spec.input(
            "system_2d",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="Set the mesh to [x,x,1]",
        )
        spec.input(
            "clean_workdir",
            valid_type=Bool,
            default=lambda: Bool(False),
            help="If `True`, work directories of all called calculation will be cleaned at the end of execution.",
        )
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.setup,
            while_(cls.should_restart)(
                if_(cls.should_run_relax)(
                    cls.run_relax,
                    cls.inspect_relax,
                ),
                cls.run_seekpath,
                if_(cls.should_run_scf)(
                    cls.run_scf,
                    cls.inspect_scf,
                ),
                if_(cls.should_run_ph)(
                    cls.run_ph,
                    cls.inspect_ph,
                ),
                if_(cls.check_ph_status_ok)(
                    if_(cls.should_run_q2r)(
                        cls.run_q2r,
                        cls.inspect_q2r,
                    ),
                    cls.run_matdyn,
                    cls.inspect_matdyn,
                ),
            ),
            cls.results,
        )
        spec.exit_code(
            300,
            "ERROR_INVALID_SCF_NODE",
            message="The scf node is invalid or does not have remote folder",
        )
        spec.exit_code(
            301,
            "ERROR_INVALID_PH_NODE",
            message="The ph node is invalid or does not have remote folder",
        )
        spec.exit_code(
            302,
            "ERROR_INVALID_Q2R_NODE",
            message="The q2r node is invalid or does not have remote folder",
        )
        spec.exit_code(
            303,
            "ERROR_INVALID_QPOINTS",
            message="No qpoints and qpoints_distance",
        )
        spec.exit_code(
            401,
            "ERROR_SUB_PROCESS_FAILED_RELAX",
            message="The relax PwBasexWorkChain sub process failed",
        )
        spec.exit_code(
            402,
            "ERROR_SUB_PROCESS_FAILED_SCF",
            message="The scf PwBasexWorkChain sub process failed",
        )
        spec.exit_code(
            403,
            "ERROR_SUB_PROCESS_FAILED_PH",
            message="The ph PhBasexWorkChain sub process failed",
        )
        spec.exit_code(
            404,
            "ERROR_SUB_PROCESS_FAILED_Q2R",
            message="The q2r Q2rBaseWorkChain sub process failed",
        )
        spec.exit_code(
            405,
            "ERROR_SUB_PROCESS_FAILED_MATDYN",
            message="The matdyn Q2rBaseWorkChain sub process failed",
        )
        spec.exit_code(
            406,
            "ERROR_IMAGINARY_FREQUENCIES",
            message="The calculation failed with an imaginary frequencies error.",
        )

        spec.output("scf_parameters", valid_type=Dict)
        spec.output("ph_parameters", valid_type=Dict)
        spec.output("q2r_force_constants")
        spec.output("matdyn_parameters", valid_type=Dict)
        spec.output("matdyn_phonon_bands")
        spec.output("output_relax_structure", required=False)

        spec.output(
            "primitive_structure",
            valid_type=StructureData,
            help="The normalized and primitivized structure for which the bands are computed.",
        )
        spec.output(
            "seekpath_parameters",
            valid_type=Dict,
            help="The parameters used in the SeeKpath call to normalize the input or relaxed structure.",
        )

    def setup(self):
        """Define the current structure in the context to be the input structure."""
        self.ctx.iteration = 0
        self.ctx.no_imaginary_frequencies = False
        self.ctx.current_structure = self.inputs.structure
        if "relax" in self.inputs:
            self.ctx.relax_inputs = AttributeDict(
                self.exposed_inputs(PwRelaxWorkChain, namespace="relax")
            )
        self.ctx.scf_inputs = AttributeDict(
            self.exposed_inputs(PwBaseWorkChain, namespace="scf")
        )
        self.ctx.ph_inputs = AttributeDict(
            self.exposed_inputs(PhBaseWorkChain, namespace="ph")
        )
        if "qpoints" in self.inputs:
            self.ctx.ph_inputs.ph.qpoints = self.inputs.get("qpoints")
        elif "qpoints_distance" in self.inputs:
            self.ctx.qpoints_distance = self.inputs.get("qpoints_distance")
        else:
            raise AttributeError("Both qpoints and qpoints_distance not found.")

    def should_restart(self):
        return (
            not self.ctx.no_imaginary_frequencies
            and self.ctx.iteration < self.inputs.max_restart_iterations.value
        )

    def should_run_relax(self):
        """If the 'relax' input namespace was specified, we relax the input structure."""
        return "relax" in self.inputs

    def check_ph_status_ok(self):
        if not self.ctx.no_imaginary_frequencies:
            # if self.ctx.iteration >= self.inputs.max_restart_iterations.value:
            #     self.report("maximum number of restart iterations exceeded")
            #     return self.exit_codes.ERROR_IMAGINARY_FREQUENCIES
            # else:
            return False
        else:
            return True
        """ if (
            not self.ctx.no_imaginary_frequencies
            and self.ctx.iteration >= self.inputs.max_restart_iterations.value
        ):
            self.report("maximum number of restart iterations exceeded")
            return self.exit_codes.ERROR_IMAGINARY_FREQUENCIES """

    def run_relax(self):
        """Run the PwRelaxWorkChain to run a relax PwCalculation."""
        inputs = self.ctx.relax_inputs

        if self.ctx.iteration == 0:
            self.ctx.kpoints_distance = inputs.base.kpoints_distance
            self.ctx.etot_conv_thr = inputs.base.pw.parameters["CONTROL"].get(
                "etot_conv_thr", 1.0e-4
            )
            self.ctx.forc_conv_thr = inputs.base.pw.parameters["CONTROL"].get(
                "forc_conv_thr", 1.0e-3
            )
            self.ctx.conv_thr = inputs.base.pw.parameters.get_attribute(
                "ELECTRONS"
            ).get("conv_thr", 1.0e-6)
            self.ctx.cutoff = inputs.base.pw.parameters.get_attribute(
                "SYSTEM"
            ).get("ecutwfc", 80)
        else:
            inputs.base.kpoints_distance = self.ctx.kpoints_distance
            inputs.base.pw.parameters["CONTROL"][
                "etot_conv_thr"
            ] = self.ctx.etot_conv_thr
            inputs.base.pw.parameters["CONTROL"][
                "forc_conv_thr"
            ] = self.ctx.forc_conv_thr
            inputs.base.pw.parameters["ELECTRONS"][
                "conv_thr"
            ] = self.ctx.conv_thr
            inputs.base.pw.parameters["SYSTEM"]["ecutwfc"] = self.ctx.cutoff

        inputs.metadata.call_link_label = "relax"
        inputs.structure = self.ctx.current_structure

        running = self.submit(PwRelaxWorkChain, **self.ctx.relax_inputs)

        self.report("launching PwRelaxWorkChain<{}>".format(running.pk))

        return ToContext(workchain_relax=running)

    def inspect_relax(self):
        """Verify that the PwRelaxWorkChain finished successfully."""
        workchain = self.ctx.workchain_relax

        if not workchain.is_finished_ok:
            self.report(
                "PwRelaxWorkChain failed with exit status {}".format(
                    workchain.exit_status
                )
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # get conv_thr
        pwbase = workchain.called[-1]
        pwcalc = pwbase.called[-1]
        self.ctx.conv_thr = pwcalc.inputs.parameters.get_attribute("ELECTRONS")[
            "conv_thr"
        ]

        self.ctx.current_structure = workchain.outputs.output_structure
        self.ctx.current_folder = workchain.outputs.remote_folder
        self.out("output_relax_structure", self.ctx.current_structure)

    def run_seekpath(self):
        """Run the structure through SeeKpath to get the primitive and normalized structure."""
        structure_formula = self.ctx.current_structure.get_formula()
        self.report(
            f"running seekpath to get primitive structure for: {structure_formula}"
        )
        kpoints_distance_for_bands = self.inputs.get(
            "matdyn_distance",
            orm.Float(0.01),
        )
        args = {
            "structure": self.ctx.current_structure,
            "reference_distance": kpoints_distance_for_bands,
            "metadata": {"call_link_label": "seekpath_structure_analysis"},
        }
        result = seekpath_structure_analysis(**args)

        self.ctx.current_structure = result["primitive_structure"]
        # ADD BY PY
        ########################################################################
        # seek path will transform the cells of some 2d structures
        # # TODO: use 2d path
        # if (
        #     "kpoints" not in self.inputs
        #     and self.inputs.system_2d.value == False
        # ):
        #     self.ctx.current_structure = result["primitive_structure"]
        # else:
        #     self.ctx.current_structure = self.inputs.structure
        ########################################################################

        # save explicit_kpoints_path for DFT bands
        # self.ctx.explicit_kpoints_path = result["explicit_kpoints"]
        if self.inputs.system_2d.value:
            kpath, kpathdict = constr2dpath(
                result["explicit_kpoints"].get_kpoints(),
                **result["explicit_kpoints"].attributes,
            )
            kpoints = KpointsData()
            kpoints.set_kpoints(kpath)
            kpoints.set_attribute("labels", kpathdict["labels"])
            kpoints.set_attribute("label_numbers", kpathdict["label_numbers"])
            self.ctx.explicit_kpoints = kpoints
        else:
            self.ctx.explicit_kpoints = result["explicit_kpoints"]

        self.out("primitive_structure", result["primitive_structure"])
        self.out("seekpath_parameters", result["parameters"])

    def should_run_scf(self):
        """If the 'scf_node' or 'ph_node' input was specified, we skip scf calc."""
        if "scf_node" in self.inputs:
            scf = load_node(self.inputs.scf_node.value)
            self.ctx.current_structure = scf.outputs.output_structure
            self.ctx.current_folder = scf.outputs.remote_folder
            self.ctx.workchain_scf = scf
            self.report(
                "Skip PwBaseWorkChain with node input pk<{}>".format(scf.pk)
            )
        return (
            "scf_node" not in self.inputs
            and "ph_node" not in self.inputs
            and "q2r_node" not in self.inputs
        )

    def run_scf(self):
        """Run the PwBaseWorkChain in scf mode on the primitive cell of input structure."""
        inputs = self.ctx.scf_inputs

        if self.ctx.iteration == 0 and "relax" not in self.inputs:
            self.ctx.kpoints_distance = inputs.kpoints_distance
            self.ctx.etot_conv_thr = inputs.pw.parameters["CONTROL"].get(
                "etot_conv_thr", 1.0e-4
            )
            self.ctx.forc_conv_thr = inputs.pw.parameters["CONTROL"].get(
                "forc_conv_thr", 1.0e-3
            )
            self.ctx.conv_thr = inputs.pw.parameters.get_attribute(
                "ELECTRONS"
            ).get("conv_thr", 1.0e-6)
        else:
            inputs.kpoints_distance = self.ctx.kpoints_distance
            inputs.pw.parameters["CONTROL"][
                "etot_conv_thr"
            ] = self.ctx.etot_conv_thr
            inputs.pw.parameters["CONTROL"][
                "forc_conv_thr"
            ] = self.ctx.forc_conv_thr
            inputs.pw.parameters["ELECTRONS"]["conv_thr"] = self.ctx.conv_thr

        inputs.metadata.call_link_label = "scf"
        inputs.pw.structure = self.ctx.current_structure
        inputs.pw.parameters = inputs.pw.parameters.get_dict()
        inputs.pw.parameters.setdefault("CONTROL", {})["calculation"] = "scf"
        inputs.pw.parameters.setdefault("ELECTRONS", {})[
            "conv_thr"
        ] = self.ctx.conv_thr

        # Make sure to carry the number of bands from the relax workchain if it was run and it wasn't explicitly defined
        # in the inputs. One of the base workchains in the relax workchain may have changed the number automatically in
        #  the sanity checks on band occupations.
        # if self.ctx.current_number_of_bands:
        #     inputs.pw.parameters.setdefault('SYSTEM', {}).setdefault(
        #         'nbnd', self.ctx.current_number_of_bands)

        inputs = prepare_process_inputs(PwBaseWorkChain, inputs)
        self.ctx.scf_inputs = inputs
        running = self.submit(PwBaseWorkChain, **inputs)

        self.report(
            "launching PwBaseWorkChain<{}> in {} mode".format(running.pk, "scf")
        )

        return ToContext(workchain_scf=running)

    def inspect_scf(self):
        """Verify that the PwBaseWorkChain for the scf run finished successfully."""
        workchain = self.ctx.workchain_scf

        if not workchain.is_finished_ok:
            self.report(
                "scf PwBaseWorkChain failed with exit status {}".format(
                    workchain.exit_status
                )
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_SCF

        self.ctx.current_folder = workchain.outputs.remote_folder

    def should_run_ph(self):
        """If the 'ph_node' input was specified, we skip scf calc."""
        flag = "ph_node" in self.inputs
        if flag:
            ph = load_node(self.inputs.ph_node.value)
            self.ctx.current_folder = ph.outputs.remote_folder
            self.ctx.workchain_ph = ph
            self.report(
                "Skip PwBaseWorkChain and PhBaseWorkChain with ph node input pk<{}>".format(
                    ph.pk
                )
            )
        return not flag and "q2r_node" not in self.inputs

    def run_ph(self):
        """Run the PhBaseWorkChain."""
        inputs = self.ctx.ph_inputs

        if self.ctx.iteration == 0:
            self.ctx.tr2_ph = inputs.ph.parameters["INPUTPH"]["tr2_ph"]
        else:
            inputs.ph.parameters["INPUTPH"]["tr2_ph"] = self.ctx.conv_thr

        inputs.ph.parent_folder = self.ctx.current_folder
        inputs.ph.parameters = inputs.ph.parameters.get_dict()

        if self.ctx.iteration == 0:
            if "qpoints" in inputs.ph:
                inputs.ph.qpoints = inputs.ph.qpoints
            else:
                inputs.ph.qpoints = create_kpoints(
                    self.ctx.current_structure,
                    self.ctx.qpoints_distance,
                    self.inputs.system_2d.value,
                )

        inputs = prepare_process_inputs(PhBaseWorkChain, inputs)
        self.ctx.ph_inputs = inputs
        running = self.submit(PhBaseWorkChain, **inputs)

        self.report(
            "launching PhBaseWorkChain<{}> in {} mode".format(running.pk, "ph")
        )

        return ToContext(workchain_ph=running)

    def inspect_ph(self):
        """Verify that the PhBaseWorkChain run finished successfully."""
        workchain = self.ctx.workchain_ph

        if not workchain.is_finished_ok:
            self.report(
                "ph PhBaseWorkChain failed with exit status {}".format(
                    workchain.exit_status
                )
            )
            if workchain.exit_status == 301:
                self.ctx.iteration += 1
                current_qpoint = workchain.outputs.current_qpoint
                self.report(
                    "The {} times to restart from relax because of imaginary frequencies in ph outputs at point {}.".format(
                        self.ctx.iteration, current_qpoint
                    )
                )
                # increase conv_thr if restarted
                self.ctx.kpoints_distance *= 0.75
                self.ctx.conv_thr *= 0.01
                self.ctx.etot_conv_thr *= 0.01
                self.ctx.forc_conv_thr *= 0.01
                self.ctx.cutoff += 20
                # increase tr2_ph if restarted
                self.ctx.tr2_ph *= 0.01
                self.report(
                    "The current kpoints_distance {}, conv_thr {}, etot_conv_thr {}, forc_conv_thr {}, tr2_ph {}.".format(
                        self.ctx.kpoints_distance,
                        self.ctx.conv_thr,
                        self.ctx.etot_conv_thr,
                        self.ctx.forc_conv_thr,
                        self.ctx.tr2_ph,
                    )
                )
                return
            else:
                return self.exit_codes.ERROR_SUB_PROCESS_FAILED_PH

        self.ctx.no_imaginary_frequencies = True
        self.ctx.current_folder = workchain.outputs.remote_folder

    def should_run_q2r(self):
        """If the 'q2r_node' input was specified, we skip scf, ph, q2r calc."""
        flag = "q2r_node" in self.inputs
        if flag:
            q2r = load_node(self.inputs.q2r_node.value)
            self.ctx.current_folder = q2r.outputs.remote_folder
            self.ctx.force_constants = q2r.outputs.force_constants
            self.ctx.workchain_q2r = q2r
            self.report(
                "Skip PwBaseWorkChain, PhBaseWorkChain and Q2r with q2r node input pk<{}>".format(
                    q2r.pk
                )
            )
        return not flag

    def run_q2r(self):
        inputs = AttributeDict(
            self.exposed_inputs(Q2rBaseWorkChain, namespace="q2r")
        )
        inputs.q2r.parent_folder = self.ctx.current_folder

        inputs = prepare_process_inputs(Q2rBaseWorkChain, inputs)
        running = self.submit(Q2rBaseWorkChain, **inputs)

        self.report(
            "launching Q2rBaseWorkChain<{}> in {} mode".format(
                running.pk, "q2r"
            )
        )
        return ToContext(workchain_q2r=running)

    def inspect_q2r(self):
        """Verify that the Q2rBaseWorkChain run finished successfully."""
        workchain = self.ctx.workchain_q2r

        if not workchain.is_finished_ok:
            self.report(
                "q2r Q2rBaseWorkChain failed with exit status {}".format(
                    workchain.exit_status
                )
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_Q2R

        self.ctx.current_folder = workchain.outputs.remote_folder
        self.ctx.force_constants = workchain.outputs.force_constants

    def run_matdyn(self):
        inputs = AttributeDict(
            self.exposed_inputs(MatdynBaseWorkChain, namespace="matdyn")
        )
        # inputs.matdyn.parent_folder = self.ctx.current_folder
        inputs.matdyn.force_constants = self.ctx.force_constants
        inputs.matdyn.kpoints = self.ctx.explicit_kpoints

        inputs = prepare_process_inputs(MatdynBaseWorkChain, inputs)
        running = self.submit(MatdynBaseWorkChain, **inputs)

        self.report(
            "launching MatdynBaseWorkChain<{}> in {} mode".format(
                running.pk, "matdyn"
            )
        )
        return ToContext(workchain_matdyn=running)

    def inspect_matdyn(self):
        """Verify that the MatdynBaseWorkChain run finished successfully."""
        workchain = self.ctx.workchain_matdyn

        if not workchain.is_finished_ok:
            self.report(
                "matdyn MatdynBaseWorkChain failed with exit status {}".format(
                    workchain.exit_status
                )
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_MATDYN

    def results(self):
        """Attach the desired output nodes directly as outputs of the workchain."""
        if not self.check_ph_status_ok():
            if self.ctx.iteration >= self.inputs.max_restart_iterations.value:
                self.report("maximum number of restart iterations exceeded")
                return self.exit_codes.ERROR_IMAGINARY_FREQUENCIES
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_PH

        self.report("workchain succesfully completed")
        try:
            self.ctx.workchain_scf
        except Exception:
            pass
        else:
            self.out(
                "scf_parameters",
                self.ctx.workchain_scf.outputs.output_parameters,
            )
        try:
            self.ctx.workchain_ph
        except Exception:
            pass
        else:
            self.out(
                "ph_parameters", self.ctx.workchain_ph.outputs.output_parameters
            )
        try:
            self.ctx.workchain_q2r
        except Exception:
            pass
        else:
            self.out(
                "q2r_force_constants",
                self.ctx.workchain_q2r.outputs.force_constants,
            )
        self.out(
            "matdyn_parameters",
            self.ctx.workchain_matdyn.outputs.output_parameters,
        )
        self.out(
            "matdyn_phonon_bands",
            self.ctx.workchain_matdyn.outputs.output_phonon_bands,
        )

    def on_terminated(self):
        """Clean the working directories of all child calculations if `clean_workdir=True` in the inputs."""
        super().on_terminated()

        if self.inputs.clean_workdir.value is False:
            self.report("remote folders will not be cleaned")
            return

        cleaned_calcs = []

        for called_descendant in self.node.called_descendants:
            if isinstance(called_descendant, CalcJobNode):
                try:
                    called_descendant.outputs.remote_folder._clean()  # pylint: disable=protected-access
                    cleaned_calcs.append(called_descendant.pk)
                except (IOError, OSError, KeyError):
                    pass

        if cleaned_calcs:
            self.report(
                "cleaned remote folders of calculations: {}".format(
                    " ".join(map(str, cleaned_calcs))
                )
            )
