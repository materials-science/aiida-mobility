import aiida.orm
from aiida_mobility.parsers.data_parser.perturbo_parser import PerturboParser
from aiida_mobility.utils import get_calc_from_folder
import os
from aiida.common import datastructures, exceptions

# from aiida_mobility.parsers.data_parser.qe2pert_parser import (
#     QE2pertParser,
# )
from aiida_mobility.calculations import BaseCalculation
from aiida import orm


class PerturboCalculation(BaseCalculation):
    """
    qe2pert calculation.
    """

    _PREFIX = "aiida"
    _DEFAULT_INPUT_FILE = "aiida.in"
    _DEFAULT_OUTPUT_FILE = "aiida.out"
    _DEFAULT_EPWAN_FILE = "aiida_epwan.h5"
    _DEFAULT_TEMPER_FILE = "aiida.temper"
    _DEFAULT_RETRIEVE_TEMP_LIST = [
        _DEFAULT_EPWAN_FILE,
    ]
    _DEFAULT_RETRIEVE_LIST = [
        _DEFAULT_INPUT_FILE,
        _DEFAULT_OUTPUT_FILE,
    ]
    _DEFAULT_PARAMETERS = {"prefix": _PREFIX, "ftemper": f"{_PREFIX}.temper"}
    _blocked_keys = [
        "prefix",
        # "boltz_kdim(1)",
        # "boltz_kdim(2)",
        # "boltz_kdim(3)",
        "ftemper",
    ]
    _DEFAULT_SETTINGS = {
        "PARENT_FOLDER_SYMLINK": True
        # npools
    }
    _default_symlink_usage = False

    @classmethod
    def define(cls, spec):
        super().define(spec)
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
            "calc_mode",
            valid_type=orm.Str,
            help="The calculation mode.",
        )
        spec.input(
            "parameters",
            valid_type=orm.Dict,
            default=lambda: orm.Dict(dict=cls._DEFAULT_PARAMETERS),
            help="Parameters to affect the way the calculation job and the parsing are performed.",
        )
        spec.input(
            "kpoints",
            valid_type=orm.KpointsData,
            required=False,
            help="kpoint to generate boltz_kdim.",
        )
        # spec.input(
        #     "qpoints",
        #     valid_type=orm.KpointsData,
        #     required=False,
        #     help="kpoint to generate boltz_kdim.",
        # )
        spec.input(
            "parent_folder",
            valid_type=orm.RemoteData,
            required=False,
            help="Parent calculation folder.",
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

    def validate_parent_calc(self):
        calc_mode = self.inputs.calc_mode.value.lower()
        try:
            parent_folder = self.inputs.parent_folder
        except exceptions.NotExistentAttributeError:
            if calc_mode in ["bands", "phdisp", "ephmat"]:
                return None
            else:
                raise exceptions.InputValidationError(
                    "Parent folder has not provided."
                )
        parent_calc = get_calc_from_folder(parent_folder)
        if calc_mode == "setup":
            if (
                parent_calc.process_type
                != "aiida.calculations:mobility.qe2pert"
            ):
                raise exceptions.InputValidationError(
                    "Parent Calculation of perturbo that in `setup` mode is not a qe2pert calculation."
                )
        elif parent_calc.process_type != "aiida.calculations:mobility.perturbo":
            raise exceptions.InputValidationError(
                f"Parent Calculation of perturbo that in `{calc_mode}` mode is not a perturbo calculation."
            )
        # TODO: verify calc_mode of parent calculations.
        return parent_calc

    def write_temper_file(
        self, folder, temperatures, fermi_levels, carrier_concentrations
    ):
        if temperatures is None:
            raise exceptions.InputValidationError(
                "You haven't explicit `temperatures` in parameters."
            )
        if carrier_concentrations is None and fermi_levels is None:
            raise exceptions.InputValidationError(
                "You haven't explicit `carrier_concentrations` or `fermi_levels` in parameters."
            )
        if carrier_concentrations is not None and len(temperatures) != len(
            carrier_concentrations
        ):
            raise exceptions.InputValidationError(
                "The length of `carrier_concentrations` != length of `temperatures` in parameters."
            )
        dst = folder.get_abs_path(self._DEFAULT_TEMPER_FILE)
        with open(dst, "w", encoding="utf8") as target:
            if carrier_concentrations is not None:
                target.write(f"{len(temperatures)}\tT")
                for i in range(0, len(temperatures)):
                    target.write(
                        f"{temperatures[i]}\t0.00\t{carrier_concentrations[i]}\n"
                    )
            else:
                target.write(f"{len(temperatures)}\t F\n")
                for i in range(0, len(temperatures)):
                    target.write(
                        f"{temperatures[i]}\t{fermi_levels[i]}\t1.0E10\n"
                    )

    def prepare_for_submission(self, folder):
        calc_mode = self.inputs.calc_mode.value.lower()
        parameters = self.inputs.parameters.get_dict()
        parameters.update({"kpoints": self.inputs.kpoints})

        if calc_mode == "setup":
            self.write_temper_file(
                folder,
                temperatures=parameters.pop("temperatures", None),
                fermi_levels=parameters.pop("fermi_levels", None),
                carrier_concentrations=parameters.pop(
                    "carrier_concentrations", None
                ),
            )

        perturbo_parser = PerturboParser(calc_mode=calc_mode, **parameters)
        parent_calc = self.validate_parent_calc()
        parent_folder = self.inputs.parent_folder

        settings = self.inputs.settings.get_dict()
        local_copy_list = []
        remote_copy_list = []
        remote_symlink_list = []
        retrieve_list = []
        retrieve_list.extend(self._DEFAULT_RETRIEVE_LIST)

        symlink = settings.pop(
            "PARENT_FOLDER_SYMLINK", self._default_symlink_usage
        )  # a boolean

        if symlink:
            remote_symlink_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        self._DEFAULT_EPWAN_FILE,
                    ),
                    self._DEFAULT_EPWAN_FILE,
                )
            )  # copy the epwan.h5 file
        else:
            remote_copy_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        self._DEFAULT_EPWAN_FILE,
                    ),
                    ".",
                )
            )  # copy the epwan.h5 file
        if calc_mode == "setup":
            retrieve_list.extend(
                [f"{self._PREFIX}.doping", f"{self._PREFIX}.dos"]
            )
        elif calc_mode == "imsigma":
            retrieve_list.extend(
                [f"{self._PREFIX}.imsigma", f"{self._PREFIX}.imsigma_mode"]
            )
            if symlink:
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            self._DEFAULT_TEMPER_FILE,
                        ),
                        self._DEFAULT_TEMPER_FILE,
                    )
                )  # copy the temper file
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.h5",
                        ),
                        f"{self._PREFIX}_tet.h5",
                    )
                )  # copy the tet.h5 file
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.kpt",
                        ),
                        f"{self._PREFIX}_tet.kpt",
                    )
                )  # copy the tet.kpt file
            else:
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            self._DEFAULT_TEMPER_FILE,
                        ),
                        ".",
                    )
                )  # copy the temper file
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.h5",
                        ),
                        ".",
                    )
                )  # copy the tet.h5 file
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.kpt",
                        ),
                        ".",
                    )
                )  # copy the tet.kpt file
        elif calc_mode == "trans":
            retrieve_list.extend(
                [f"{self._PREFIX}.tdf", f"{self._PREFIX}.cond"]
            )
            if symlink:
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            self._DEFAULT_TEMPER_FILE,
                        ),
                        self._DEFAULT_TEMPER_FILE,
                    )
                )  # copy the temper file
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.h5",
                        ),
                        f"{self._PREFIX}_tet.h5",
                    )
                )  # copy the tet.h5 file
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}.imsigma",
                        ),
                        f"{self._PREFIX}.imsigma",
                    )
                )  # copy the imsigma file
            else:
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            self._DEFAULT_TEMPER_FILE,
                        ),
                        ".",
                    )
                )  # copy the temper file
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}_tet.h5",
                        ),
                        ".",
                    )
                )  # copy the tet.h5 file
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            f"{self._PREFIX}.imsigma",
                        ),
                        ".",
                    )
                )  # copy the imsigma file

        # write input file
        dst = folder.get_abs_path(self._DEFAULT_INPUT_FILE)
        perturbo_parser.write(dst)

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
        calcinfo.retrieve_list = retrieve_list
        # calcinfo.retrieve_temporary_list = self._DEFAULT_RETRIEVE_TEMP_LIST

        return calcinfo