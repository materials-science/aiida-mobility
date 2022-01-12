import aiida.orm
from ase.atoms import default
from sqlalchemy.sql.expression import true
from aiida_mobility.calculations.perturbo import PerturboCalculation
from aiida_mobility.utils import get_calc_from_folder
from aiida.common import exceptions
from aiida.common.extendeddicts import AttributeDict
from aiida.engine.processes.workchains.context import ToContext
from aiida_quantumespresso.utils.mapping import prepare_process_inputs
from plumpy.workchains import if_
from aiida_mobility.calculations.qe2pert import QE2PertCalculation
from aiida_mobility.calculations.ph_recover import PhRecoverCalculation
from aiida.engine.processes.workchains.workchain import WorkChain
from aiida import orm
import numpy as np


def validate_inputs(inputs, ctx=None):  # pylint: disable=unused-argument
    pass


class PertuborWorkChain(WorkChain):
    _QE_DVSCF_PREFIX = QE2PertCalculation._QE_DVSCF_PREFIX
    _DEFAULT_SETTINGS = {}
    _DEFAULT_METADATA_OPTIONS = {
        "resources": {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        },
        "withmpi": False,
    }

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input(
            "metadata_options",
            valid_type=orm.Dict,
            default=lambda: orm.Dict(dict=cls._DEFAULT_METADATA_OPTIONS),
            help="options designated for calculation.",
        )
        spec.expose_inputs(
            QE2PertCalculation,
            namespace="qe2pert",
            exclude=("kpoints", "clean_workdir", "dry_run"),
        )
        # spec.expose_inputs(
        #     PerturboCalculation,
        #     namespace="pert",
        #     exclude=(
        #         "calc_mode",
        #         "parameters",
        #         "parent_folder",
        #         "clean_workdir",
        #         "dry_run",
        #     ),
        # )
        spec.input("pert_code", valid_type=orm.Code)
        spec.input(
            "bands_energy_threshold",
            valid_type=orm.Float,
            default=lambda: orm.Float(0.3),
            help="Energy range of considered bands (e.g. fermi energy +/- 0.3, defalut is 0.3).",
        )
        spec.input(
            "max_T",
            valid_type=orm.Int,
            required=False,
            help="Max temperature.",
        )
        spec.input(
            "min_T",
            valid_type=orm.Int,
            required=False,
            help="Min temperature.",
        )
        spec.input(
            "T_step",
            valid_type=orm.Int,
            required=False,
            help="Temperature change step.",
        )
        spec.input(
            "carrier_concentration",
            valid_type=orm.Float,
            required=False,
            help="Carrier concentration.",
        )
        spec.input(
            "phfreq_cutoff",
            valid_type=orm.Float,
            default=lambda: orm.Float(1),
            help="the cutoff energy for the phonons. Phonon with their energy smaller than the cutoff (in meV) is ignored; 0.5-2 meV is recommended.",
        )
        spec.input(
            "delta_smear",
            valid_type=orm.Float,
            default=lambda: orm.Float(10),
            help="the broadening (in meV) used for the Gaussian function used to model the Dirac delta function.",
        )
        spec.input(
            "sampling",
            valid_type=orm.Str,
            required=False,
            help="sampling method for random q points used in e-ph self-energy calculation, `uniform` and `cauchy`[useful for polar materials] are available. If not set, `fqlist` will be same with `fklist`.",
        )
        spec.input(
            "nsamples",
            valid_type=orm.Int,
            default=lambda: orm.Int(100000),
            help="Number of q-points for the summation over the q-points in imsigma calculation.",
        )
        spec.input(
            "cauchy_scale",
            valid_type=orm.Float,
            default=lambda: orm.Float(1.0),
            help="Scale parameter gamma for the Cauchy distribution; used when sampling='cauchy'.",
        )
        spec.input(
            "boltz_nstep",
            valid_type=orm.Int,
            default=lambda: orm.Int(0),
            help="Contains the maximum number of iterations in the iterative scheme for solving Boltzmann equation. Default is `0`, which uses RTA.",
        )
        spec.input(
            "clean_workdir",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="If `True`, work directories of all called calculation will be cleaned at the end of execution.",
        )
        spec.input(
            "settings",
            valid_type=orm.Dict,
            required=False,
            default=lambda: orm.Dict(dict=cls._DEFAULT_SETTINGS),
            help="Optional parameters to affect the way the calculation job and the parsing are performed.",
        )
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.setup,
            if_(cls.should_run_ph_recover)(
                cls.run_ph_recover, cls.inspect_ph_recover
            ),
            cls.run_qe2pert,
            cls.run_pert_setup,
            cls.run_pert_imsigma,
            cls.run_pert_trans,
            if_(cls.should_calculate_hole)(
                cls.run_pert_setup, cls.run_pert_imsigma, cls.run_pert_trans
            ),
            cls.results,
        )
        spec.exit_code(
            300,
            "ERROR_INVALID_SCF_NODE",
            message="The scf node is invalid or does not have remote folder",
        )
        spec.exit_code(
            400, "ERROR_SUB_PROCESS_FAILED", message="The sub process failed"
        )

    def get_common_metadata_options(self):
        return self.inputs.metadata_options.get_dict()

    def setup(self):
        self.ctx.should_run_ph_recover = True
        self.ctx.should_calculate_hole = False
        self.ctx.ph_inputs = AttributeDict(
            {"metadata": {"options": self.get_common_metadata_options()}}
        )
        self.ctx.qe2pert_inputs = AttributeDict(
            self.exposed_inputs(QE2PertCalculation, namespace="qe2pert")
        )
        # self.ctx.pert_inputs = AttributeDict(
        #     self.exposed_inputs(PerturboCalculation, namespace="pert")
        # )
        self.ctx.pert_code = self.inputs.pert_code
        self.validate_ph_folder()
        self.validate_wannier_folder()
        if (
            "max_T" in self.inputs
            and "min_T" in self.inputs
            and "T_step" in self.inputs
        ):
            self.ctx.temperatures = np.arange(
                self.inputs.min_T.value,
                self.inputs.max_T.value,
                self.inputs.T_step.value,
            )
        else:
            self.ctx.temperatures = [300]

        if "carrier_concentration" in self.inputs:
            self.ctx.carrier_concentrations = [
                self.inputs.carrier_concentration.value
            ] * len(self.ctx.temperatures)
        elif self.ctx.bands_info.get("type") == "metal":
            self.ctx.fermi_levels = [
                self.ctx.bands_info.get("fermi_energy")
            ] * len(self.ctx.temperatures)
        else:
            raise exceptions.InputValidationError(
                "You have to explict `carrier_concentration` or the structure must be matel."
            )

    def validate_wannier_folder(self):
        parent_folder = self.ctx.qe2pert_inputs.wannier_folder
        parent_calc = get_calc_from_folder(parent_folder)
        if parent_calc.process_type != "aiida.calculations:wannier90.wannier90":
            raise exceptions.InputValidationError(
                "Parent Calculation is not a wannier90 calculation."
            )

        wannier90 = parent_calc.caller
        self.ctx.kpoints = wannier90.inputs.scf__kpoints

        wannier_parameters = parent_calc.outputs.output_parameters.get_dict()
        number_wfs = wannier_parameters.get("number_wfs", None)
        if number_wfs is None:
            raise exceptions.InputValidationError(
                "Wannier90 calculation has no `number_wfs` data."
            )
        omega_avg = (
            wannier_parameters.get("Omega_D", 0)
            + wannier_parameters.get("Omega_I", 0)
            + wannier_parameters.get("Omega_OD", 0)
        ) / number_wfs
        settings = self.inputs.settings.get_dict()
        if omega_avg > settings.get("max_OmegaTOT_average", 10):
            raise exceptions.InputValidationError(
                "The average of OmegaTOT <{}|{}> of wannier is too large. You'd better check the interpolated bands or increase `max_OmegaTOT_average` in `settings` input(default is 10).".format(
                    omega_avg, number_wfs
                )
            )

        bands_info = get_bands_info(
            parent_calc.outputs.interpolated_bands.get_array("bands"),
            parent_calc.inputs.parameters.get_attribute("fermi_energy"),
            distance=self.inputs.bands_energy_threshold.value,
        )
        self.ctx.bands_info = bands_info

    def validate_ph_folder(self):
        parent_folder = self.ctx.qe2pert_inputs.ph_folder
        parent_calc = get_calc_from_folder(parent_folder)

        if (
            parent_calc.process_type
            == "aiida_mobility.calculations.ph_recover.PhRecoverCalculation"
        ):
            self.ctx.should_run_ph_recover = False
        elif (
            parent_calc.process_type != "aiida.calculations:quantumespresso.ph"
        ):
            raise exceptions.InputValidationError(
                "Parent Calculation is not a ph calculation."
            )

        self.ctx.ph_folder = parent_folder
        self.ctx.ph_code = parent_calc.inputs.code

    def should_run_ph_recover(self):
        return self.ctx.should_run_ph_recover

    def run_ph_recover(self):
        ph_inputs = self.ctx.ph_inputs
        ph_inputs.parent_folder = self.ctx.ph_folder
        ph_inputs.code = self.ctx.ph_code

        inputs = prepare_process_inputs(PhRecoverCalculation, ph_inputs)
        self.ctx.ph_inputs = inputs
        running = self.submit(PhRecoverCalculation, **inputs)

        self.report(
            "launching PhRecoverCalculation<{}> in {} mode".format(
                running.pk, "ph"
            )
        )

        return ToContext(workchain_ph=running)

    def inspect_ph_recover(self):
        if not self.ctx.workchain_ph.is_finished_ok:
            self.report(
                "PhRecoverCalculation failed with exit status {}".format(
                    self.ctx.workchain_ph.exit_status
                )
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED

        self.ctx.ph_folder = self.ctx.workchain_ph.outputs.remote_folder

    def run_qe2pert(self):
        inputs = self.ctx.qe2pert_inputs
        inputs.ph_folder = self.ctx.ph_folder
        inputs.setdefault(
            "metadata", {"options": self.get_common_metadata_options()}
        )
        running = self.submit(QE2PertCalculation, **inputs)

        self.report("launching QE2PertCalculation<{}>.".format(running.pk))

        return ToContext(workchain_qe2pert=running)

    def should_calculate_hole(self):
        if self.ctx.bands_info.get("type", None) != "metal":
            self.ctx.should_calculate_hole = True
        return self.ctx.should_calculate_hole

    def run_pert_setup(self):
        inputs = AttributeDict(
            {"metadata": {"options": self.get_common_metadata_options()}}
        )
        inputs.parent_folder = self.ctx.workchain_qe2pert.outputs.remote_folder
        inputs.calc_mode = "setup"
        inputs.code = self.ctx.pert_code
        params = {}
        common_pert_params = {}
        if self.ctx.should_calculate_hole:
            common_pert_params["hole"] = true
            common_pert_params["band_min"] = self.ctx.bands_info.get(
                "hole_min_band"
            )
            common_pert_params["band_max"] = self.ctx.bands_info.get(
                "hole_max_band"
            )
            common_pert_params["boltz_emin"] = self.ctx.bands_info.get(
                "hole_e_min"
            )
            common_pert_params["boltz_emax"] = self.ctx.bands_info.get(
                "hole_e_max"
            )
        else:
            common_pert_params["band_min"] = self.ctx.bands_info.get(
                "el_min_band"
            )
            common_pert_params["band_max"] = self.ctx.bands_info.get(
                "el_max_band"
            )
            common_pert_params["boltz_emin"] = self.ctx.bands_info.get(
                "el_e_min"
            )
            common_pert_params["boltz_emax"] = self.ctx.bands_info.get(
                "el_e_max"
            )
        self.ctx.common_pert_params = common_pert_params
        params.update(common_pert_params)
        params.update({"temperatures": self.ctx.temperatures})
        if "carrier_concentration" in self.inputs:
            params.update(
                {"carrier_concentrations": self.ctx.carrier_concentrations}
            )
        elif self.ctx.bands_info.get("type") == "metal":
            params.update({"fermi_levels": self.ctx.fermi_levels})

        inputs.parameters = orm.Dict(dict=params)

        if "kpoints" not in inputs:
            scf_kpoints = self.ctx.kpoints
            mesh = scf_kpoints.get_kpoints_mesh()
            mesh = np.dot(mesh, 10)
            kpoints = orm.KpointsData()
            kpoints.set_kpoints_mesh(mesh)
            inputs.kpoints = kpoints

        running = self.submit(PerturboCalculation, **inputs)

        self.report(
            "launching PerturboCalculation in `setup` mode<{}>.".format(
                running.pk
            )
        )

        if self.ctx.should_calculate_hole:
            return ToContext(workchain_pert_setup_hole=running)
        else:
            return ToContext(workchain_pert_setup=running)

    def run_pert_imsigma(self):
        inputs = AttributeDict(
            {"metadata": {"options": self.get_common_metadata_options()}}
        )
        inputs.code = self.ctx.pert_code
        if self.ctx.should_calculate_hole:
            inputs.parent_folder = (
                self.ctx.workchain_pert_setup_hole.outputs.remote_folder
            )
        else:
            inputs.parent_folder = (
                self.ctx.workchain_pert_setup.outputs.remote_folder
            )

        inputs.calc_mode = "imsigma"
        params = {}
        params.update(self.ctx.common_pert_params)
        params.update(
            {
                "phfreq_cutoff": self.inputs.phfreq_cutoff.value,
                "delta_smear": self.inputs.delta_smear.value,
            }
        )

        if "sampling" in self.inputs:
            params.update(
                {
                    "sampling": self.inputs.sampling.value,
                    "nsamples": self.inputs.nsamples.value,
                }
            )

            if self.inputs.sampling.value == "cauchy_scale":
                params.update({"cauchy_scale": self.inputs.cauchy_scale.value})

        running = self.submit(PerturboCalculation, **inputs)

        self.report(
            "launching PerturboCalculation in `imsigma` mode<{}>.".format(
                running.pk
            )
        )

        if self.ctx.should_calculate_hole:
            return ToContext(workchain_pert_imsigma_hole=running)
        else:
            return ToContext(workchain_pert_imsigma=running)

    def run_pert_trans(self):
        inputs = AttributeDict(
            {"metadata": {"options": self.get_common_metadata_options()}}
        )
        inputs.code = self.ctx.pert_code
        if self.ctx.should_calculate_hole:
            inputs.parent_folder = (
                self.ctx.workchain_pert_imsigma_hole.outputs.remote_folder
            )
        else:
            inputs.parent_folder = (
                self.ctx.workchain_pert_imsigma.outputs.remote_folder
            )
        inputs.calc_mode = "trans"
        params = {}
        params.update(self.ctx.common_pert_params)

        boltz_nstep = self.inputs.boltz_nstep.value
        params["boltz_nstep"] = boltz_nstep
        if boltz_nstep != 0:
            params.update(
                {
                    "phfreq_cutoff": self.inputs.phfreq_cutoff.value,
                    "delta_smear": self.inputs.delta_smear.value,
                }
            )

        running = self.submit(PerturboCalculation, **inputs)

        self.report(
            "launching PerturboCalculation in `trans` mode<{}>.".format(
                running.pk
            )
        )

        if self.ctx.should_calculate_hole:
            return ToContext(workchain_pert_trans_hole=running)
        else:
            return ToContext(workchain_pert_trans=running)

    def results(self):
        self.report(self.ctx.workchain_ph.outputs.out_parameters)


def get_bands_info(bands, fermi_energy, distance=0.3):
    bands_info = {"fermi_energy": fermi_energy}
    # if np.isclose(np.min(np.abs(bands - fermi_energy)), 0):
    bound = bands[bands < fermi_energy].shape[0] / bands.shape[0]
    if bound % 1 != 0:  # metal
        # raise ValueError("The fermi level is over some bands.")
        calc_bands = []
        for i in range(0, bands.shape[1]):
            band = bands[:, i]
            if np.min(np.abs(band - fermi_energy)) < distance:
                calc_bands.append(i)
        if len(calc_bands) == 0:
            raise ValueError(
                "No bands between fermi energy {} +- {}.".format(
                    fermi_energy, distance
                )
            )
        bands_info.update(
            {
                "type": "metal",
                "el_max_band": np.max(calc_bands) + 1,
                "el_min_band": np.min(calc_bands) + 1,
                "el_e_max": fermi_energy + distance,
                "el_e_min": fermi_energy - distance,
            }
        )
    else:
        # semi-conductor
        bound = int(bound)
        el_min = np.min(bands[:, bound:])
        hole_max = np.max(bands[:, :bound])
        calc_el_bands = []
        calc_hole_bands = []
        for i in range(bound, bands.shape[1]):
            band = bands[:, i]
            if np.min(np.abs(band - el_min)) < distance:
                calc_el_bands.append(i)

        if len(calc_el_bands) == 0:
            raise ValueError("Cannot get el bands from bands data.")

        for i in range(0, bound):
            band = bands[:, i]
            if np.min(np.abs(band - hole_max)) < distance:
                calc_hole_bands.append(i)

        if len(calc_el_bands) == 0:
            raise ValueError("Cannot get hole bands from bands data.")

        bands_info.update(
            {
                "el_max_band": np.max(calc_el_bands) + 1,
                "el_min_band": np.min(calc_el_bands) + 1,
                "el_e_max": np.max(bands[np.max(calc_el_bands)]),
                "el_e_min": el_min,
                "hole_max_band": np.max(calc_hole_bands) + 1,
                "hole_min_band": np.min(calc_hole_bands) + 1,
                "hole_e_max": hole_max,
                "hole_e_min": np.min(bands[np.min(calc_hole_bands)]),
            }
        )
    return bands_info
