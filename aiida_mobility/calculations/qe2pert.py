from aiida_mobility.utils import get_calc_from_folder
import os
from aiida.common import datastructures, exceptions
from aiida_mobility.parsers.data_parser.qe2pert_parser import (
    QE2pertParser,
)
from aiida_mobility.calculations import BaseCalculation
from aiida import orm
import numpy as np


class QE2PertCalculation(BaseCalculation):
    """
    qe2pert calculation.
    """

    _PREFIX = "aiida"
    _DEFAULT_INPUT_FILE = "aiida.in"
    _DEFAULT_OUTPUT_FILE = "aiida.out"
    _DEFAULT_EPWAN_FILE = "aiida_epwan.h5"
    _DEFAULT_RETRIEVE_TEMP_LIST = [
        _DEFAULT_EPWAN_FILE,
    ]
    _DEFAULT_RETRIEVE_LIST = [
        _DEFAULT_INPUT_FILE,
        _DEFAULT_OUTPUT_FILE,
    ]
    _DEFAULT_SETTINGS = {
        "PARENT_FOLDER_SYMLINK": True
        # npools
    }
    _INPUT_PH_SUBFOLDER = "./save/"
    _INPUT_NSCF_SUBFOLDER = "./out/"
    _QE_INPUT_SUBFOLDER = "./out/"
    _QE_OUTPUT_SUBFOLDER = "./out/"
    _QE_FOLDER_DYNAMICAL_MATRIX = "DYN_MAT"
    _QE_OUTPUT_DYNAMICAL_MATRIX_PREFIX = os.path.join(
        _QE_FOLDER_DYNAMICAL_MATRIX, "dynamical-matrix-"
    )
    _QE_DVSCF_PREFIX = "dvscf"
    _default_symlink_usage = False

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.inputs["metadata"]["options"]["parser_name"].default = "qe2pert"

        spec.input(
            "metadata.options.input_filename",
            valid_type=str,
            default=cls._DEFAULT_INPUT_FILE,
        )
        spec.input(
            "metadata.options.output_filename",
            valid_type=str,
            default=cls._DEFAULT_OUTPUT_FILE,
        )
        spec.input("metadata.options.withmpi", valid_type=bool, default=True)
        spec.input(
            "kpoints",
            valid_type=orm.KpointsData,
            required=False,
            help="kpoint mesh.",
        )
        spec.input(
            "dft_band_min",
            valid_type=orm.Int,
            required=False,
            help="Determine the range of bands we are interested in, and should be the same as the values used in the Wannierization process. Defaul is `1`.",
        )
        spec.input(
            "dft_band_max",
            valid_type=orm.Int,
            required=False,
            help="Determine the range of bands we are interested in, and should be the same as the values used in the Wannierization process. If not set, will read `number_of_bands` from nscf calculation.",
        )
        spec.input(
            "num_wann",
            valid_type=orm.Int,
            required=False,
            help="The number of Wannier functions. If not set, will read `number_wfs` from wannier90 calculation.",
        )
        spec.input(
            "lwannier",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(True),
            help="A logical flag. When it is .true., the e-ph matrix elements are computed using the Bloch wave functions rotated with the Wannier unitary matrix. If .false., the e-ph matrix elements are computed using the Bloch wave functions, and the e-ph matrix elements are then rotated using the Wannier unitary matrix.",
        )
        # spec.input(
        #     "load_ephmat",
        #     valid_type=orm.Int,
        #     default=lambda: orm.Bool(False),
        #     help="A logical flag. If .true., reuse e-ph matrix elements in Bloch function basis computed previously.",
        # )
        spec.input(
            "system_2d",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="If the materials is two-dimensional.",
        )
        spec.input(
            "ph_folder",
            valid_type=orm.RemoteData,
            help="phonon calculation folder.",
        )
        spec.input(
            "nscf_folder",
            valid_type=orm.RemoteData,
            help="nscf calculation folder.",
        )
        spec.input(
            "wannier_folder",
            valid_type=orm.RemoteData,
            help="wannier calculation folder.",
        )
        spec.input(
            "settings",
            valid_type=orm.Dict,
            default=lambda: orm.Dict(dict=cls._DEFAULT_SETTINGS),
            help="Optional parameters to affect the way the calculation job and the parsing are performed.",
        )
        spec.output(
            "output_parameters",
            valid_type=orm.Dict,
            help="The `output_parameters` output node of the successful calculation.",
        )
        spec.exit_code(
            300,
            "ERROR_NO_RETRIEVED_TEMPORARY_FOLDER",
            message="The retrieved temporary folder could not be accessed.",
        )
        spec.exit_code(
            301,
            "ERROR_NO_RETRIEVED_FOLDER",
            message="The retrieved folder could not be accessed.",
        )
        spec.exit_code(
            302,
            "ERROR_OUTPUT_STDOUT_MISSING",
            message="The retrieved folder did not contain the required stdout output file.",
        )
        spec.exit_code(
            303,
            "ERROR_OUTPUT_FILES",
            message="Expected output files did not generate.",
        )

        spec.exit_code(
            310,
            "ERROR_OUTPUT_STDOUT_READ",
            message="The stdout output file could not be read.",
        )
        spec.exit_code(
            311,
            "ERROR_OUTPUT_STDOUT_PARSE",
            message="The stdout output file could not be parsed.",
        )
        spec.exit_code(
            312,
            "ERROR_OUTPUT_STDOUT_INCOMPLETE",
            message="The stdout output file was incomplete probably because the calculation got interrupted.",
        )

    def get_nbands(self):
        parent_folder = self.inputs.nscf_folder
        parent_calc = get_calc_from_folder(parent_folder)
        if parent_calc.process_type != "aiida.calculations:quantumespresso.pw":
            raise exceptions.InputValidationError(
                "Parent Calculation is not a nscf calculation."
            )
        nscf_parameters = parent_calc.outputs.output_parameters.get_dict()
        nbands = nscf_parameters.get("number_of_bands", None)
        if nbands is None:
            raise exceptions.InputValidationError(
                "NSCF calculation has no `number_of_bands` data."
            )
        return nbands

    def get_number_wfs_and_kpoints(self):
        parent_folder = self.inputs.wannier_folder
        parent_calc = get_calc_from_folder(parent_folder)
        if parent_calc.process_type != "aiida.calculations:wannier90.wannier90":
            raise exceptions.InputValidationError(
                "Parent Calculation is not a wannier90 calculation."
            )
        wannier_parameters = parent_calc.outputs.output_parameters.get_dict()
        number_wfs = wannier_parameters.get("number_wfs", None)
        if number_wfs is None:
            raise exceptions.InputValidationError(
                "Wannier90 calculation has no `number_wfs` data."
            )

        wannier90 = parent_calc.caller
        kpoints = wannier90.inputs.scf__kpoints
        return number_wfs, kpoints

    def prepare_for_submission(self, folder):
        nbands = self.get_nbands()
        number_wfs, kpoints = self.get_number_wfs_and_kpoints()
        dft_band_min = self.inputs.get("dft_band_min", 1)
        dft_band_max = self.inputs.get("dft_band_max", nbands)
        num_wann = self.inputs.get("num_wann", number_wfs)

        settings = self.inputs.settings.get_dict()
        local_copy_list = []
        remote_copy_list = []
        remote_symlink_list = []

        symlink = settings.pop(
            "PARENT_FOLDER_SYMLINK", self._default_symlink_usage
        )  # a boolean

        # copy ph data from remote folder
        ph_folder = self.inputs.ph_folder
        ph_calcs = ph_folder.get_incoming(node_class=orm.CalcJobNode).all()
        if not ph_calcs:
            raise exceptions.NotExistent(
                f"parent_folder<{ph_folder.pk}> has no parent calculation"
            )
        elif len(ph_calcs) > 1:
            raise exceptions.UniquenessError(
                f"parent_folder<{ph_folder.pk}> has multiple parent calculations"
            )
        ph_calc = ph_calcs[0].node
        folder.get_subfolder(self._INPUT_PH_SUBFOLDER, create=True)

        if symlink:
            remote_symlink_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_FOLDER_DYNAMICAL_MATRIX,
                        "*",
                    ),
                    self._INPUT_PH_SUBFOLDER,
                )
            )
        else:
            remote_copy_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_FOLDER_DYNAMICAL_MATRIX,
                        "*",
                    ),
                    self._INPUT_PH_SUBFOLDER,
                )
            )  # copy dyn files

        number_of_qpoints = ph_calc.outputs.output_parameters.get_attribute(
            "number_of_qpoints", None
        )
        if not number_of_qpoints:
            raise exceptions.NotExistent(
                f"parent_folder<{ph_folder.pk}>'s parent calculation has no number_of_qpoints."
            )

        dvscf_prefix = f"{self._PREFIX}.{self._QE_DVSCF_PREFIX}"

        if symlink:
            remote_symlink_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                        "_ph0",
                        f"{dvscf_prefix}1",
                    ),
                    os.path.join(
                        self._INPUT_PH_SUBFOLDER, f"{dvscf_prefix}_q1"
                    ),
                )
            )  # link dvscf(default: `aiida.dvscf1`) of q1 to `aiida.dvscf_q1`

            for idx in range(
                2, number_of_qpoints + 1
            ):  # link dvscf(default: `aiida.dvscf1`) of q* to `aiida.dvscf_q*`
                remote_symlink_list.append(
                    (
                        ph_folder.computer.uuid,
                        os.path.join(
                            ph_folder.get_remote_path(),
                            self._QE_OUTPUT_SUBFOLDER,
                            "_ph0",
                            f"{self._PREFIX}.q_{idx}",
                            f"{dvscf_prefix}1",
                        ),
                        os.path.join(
                            self._INPUT_PH_SUBFOLDER, f"{dvscf_prefix}_q{idx}"
                        ),
                    )
                )

            remote_symlink_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                        "_ph0",
                        f"{self._PREFIX}.phsave",
                    ),
                    os.path.join(
                        self._INPUT_PH_SUBFOLDER, f"{self._PREFIX}.phsave"
                    ),
                )
            )  # link `aiida.phsave`
        else:
            remote_copy_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                        "_ph0",
                        f"{dvscf_prefix}1",
                    ),
                    os.path.join(
                        self._INPUT_PH_SUBFOLDER, f"{dvscf_prefix}_q1"
                    ),
                )
            )  # copy dvscf(default: `aiida.dvscf1`) of q1 to `aiida.dvscf_q1`

            for idx in range(
                2, number_of_qpoints + 1
            ):  # copy dvscf(default: `aiida.dvscf1`) of q* to `aiida.dvscf_q*`
                remote_copy_list.append(
                    (
                        ph_folder.computer.uuid,
                        os.path.join(
                            ph_folder.get_remote_path(),
                            self._QE_OUTPUT_SUBFOLDER,
                            "_ph0",
                            f"{self._PREFIX}.q_{idx}",
                            f"{dvscf_prefix}1",
                        ),
                        os.path.join(
                            self._INPUT_PH_SUBFOLDER, f"{dvscf_prefix}_q{idx}"
                        ),
                    )
                )

            remote_copy_list.append(
                (
                    ph_folder.computer.uuid,
                    os.path.join(
                        ph_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                        "_ph0",
                        f"{self._PREFIX}.phsave",
                    ),
                    self._INPUT_PH_SUBFOLDER,
                )
            )  # copy `aiida.phsave`

        # copy nscf data from remote folder
        nscf_folder = self.inputs.nscf_folder
        if symlink:
            folder.get_subfolder(self._INPUT_NSCF_SUBFOLDER, create=True)
            remote_symlink_list.append(
                (
                    nscf_folder.computer.uuid,
                    os.path.join(
                        nscf_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                        "*",
                    ),
                    self._INPUT_NSCF_SUBFOLDER,
                )
            )
        else:
            remote_copy_list.append(
                (
                    nscf_folder.computer.uuid,
                    os.path.join(
                        nscf_folder.get_remote_path(),
                        self._QE_OUTPUT_SUBFOLDER,
                    ),
                    ".",
                )
            )

        # copy wannier data form remote folder
        wannier_folder = self.inputs.wannier_folder
        if symlink:
            remote_symlink_list.append(
                (
                    wannier_folder.computer.uuid,
                    os.path.join(
                        wannier_folder.get_remote_path(),
                        f"{self._PREFIX}_centres.xyz",
                    ),
                    f"{self._PREFIX}_centres.xyz",
                )
            )  # link aiida_centres.xyz
            remote_symlink_list.append(
                (
                    wannier_folder.computer.uuid,
                    os.path.join(
                        wannier_folder.get_remote_path(), f"{self._PREFIX}_u*"
                    ),
                    ".",
                )
            )  # link aiida_u.mat and aiida_u_dis.mat
        else:
            remote_copy_list.append(
                (
                    wannier_folder.computer.uuid,
                    os.path.join(
                        wannier_folder.get_remote_path(),
                        f"{self._PREFIX}_centres.xyz",
                    ),
                    ".",
                )
            )  # copy aiida_centres.xyz
            remote_copy_list.append(
                (
                    wannier_folder.computer.uuid,
                    os.path.join(
                        wannier_folder.get_remote_path(), f"{self._PREFIX}_u*"
                    ),
                    ".",
                )
            )  # copy aiida_u.mat and aiida_u_dis.mat
        # TODO: whether or not to copy aiida_band.kpt

        # write input file
        dst = folder.get_abs_path(self._DEFAULT_INPUT_FILE)
        qe2pert_parser = QE2pertParser(
            **{
                "prefix": self._PREFIX,
                "outdir": "./out",
                "phdir": self._INPUT_PH_SUBFOLDER,
                "kpoints": self.inputs.kpoints
                if "kpoints" in self.inputs
                else kpoints,
                "dft_band_min": dft_band_min,
                "dft_band_max": dft_band_max,
                "num_wann": num_wann,
                "lwannier": self.inputs.lwannier.value,
                "system_2d": self.inputs.system_2d.value,
            }
        )
        qe2pert_parser.write(dst)

        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid

        npools = settings.get(
            "npools",
            self.inputs.metadata.options.resources["num_mpiprocs_per_machine"],
        )
        codeinfo.cmdline_params = list(settings.pop("CMDLINE", [])) + [
            "-npools",
            npools,
            "-in",
            self.metadata.options.input_filename,
        ]
        codeinfo.stdout_name = self.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.remote_symlink_list = remote_symlink_list
        calcinfo.retrieve_list = self._DEFAULT_RETRIEVE_LIST
        calcinfo.retrieve_temporary_list = self._DEFAULT_RETRIEVE_TEMP_LIST

        return calcinfo