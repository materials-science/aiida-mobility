# -*- coding: utf-8 -*-
"""Plugin to create a Quantum Espresso ph.x input file."""
import os
import numpy

from aiida import orm
from aiida.common import datastructures, exceptions
from aiida_quantumespresso.utils.convert import convert_input_to_namelist_entry

from aiida_quantumespresso.calculations.base import CalcJob


class PhRecoverCalculation(CalcJob):
    """`CalcJob` implementation for the ph.x code of Quantum ESPRESSO."""

    # Keywords that cannot be set by the user but will be set by the plugin

    _use_kpoints = True

    # Default input and output files
    _PREFIX = "aiida"
    _DEFAULT_INPUT_FILE = "aiida.in"
    _DEFAULT_OUTPUT_FILE = "aiida.out"
    _OUTPUT_XML_TENSOR_FILE_NAME = "tensors.xml"
    _OUTPUT_SUBFOLDER = "./out/"
    _FOLDER_DRHO = "FILDRHO"
    _DRHO_PREFIX = "drho"
    _DVSCF_PREFIX = "dvscf"
    _DRHO_STAR_EXT = "drho_rot"
    _FOLDER_DYNAMICAL_MATRIX = "DYN_MAT"
    _VERBOSITY = "high"
    _OUTPUT_DYNAMICAL_MATRIX_PREFIX = os.path.join(
        _FOLDER_DYNAMICAL_MATRIX, "dynamical-matrix-"
    )

    _DEFAULT_SETTINGS = {"PARENT_FOLDER_SYMLINK": True}
    _default_symlink_usage = False

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        # yapf: disable
        super().define(spec)
        spec.input('metadata.options.input_filename', valid_type=str, default=cls._DEFAULT_INPUT_FILE)
        spec.input('metadata.options.output_filename', valid_type=str, default=cls._DEFAULT_OUTPUT_FILE)
        spec.input('metadata.options.parser_name', valid_type=str, default='quantumespresso.ph')
        spec.input('metadata.options.withmpi', valid_type=bool, default=True)
        spec.input('settings', valid_type=orm.Dict, default=orm.Dict(dict=cls._DEFAULT_SETTINGS), help='')
        spec.input('parent_folder', valid_type=orm.RemoteData,
            help='parent `PhCalculation`.')

        spec.output('output_parameters', valid_type=orm.Dict)
        spec.default_output_node = 'output_parameters'

        # Unrecoverable errors: required retrieved files could not be read, parsed or are otherwise incomplete
        spec.exit_code(302, 'ERROR_OUTPUT_STDOUT_MISSING',
            message='The retrieved folder did not contain the required stdout output file.')
        spec.exit_code(305, 'ERROR_OUTPUT_FILES',
            message='Both the stdout and XML output files could not be read or parsed.')
        spec.exit_code(310, 'ERROR_OUTPUT_STDOUT_READ',
            message='The stdout output file could not be read.')
        spec.exit_code(311, 'ERROR_OUTPUT_STDOUT_PARSE',
            message='The stdout output file could not be parsed.')
        spec.exit_code(312, 'ERROR_OUTPUT_STDOUT_INCOMPLETE',
            message='The stdout output file was incomplete probably because the calculation got interrupted.')
        spec.exit_code(350, 'ERROR_UNEXPECTED_PARSER_EXCEPTION',
            message='The parser raised an unexpected exception.')

        # Significant errors but calculation can be used to restart
        spec.exit_code(400, 'ERROR_OUT_OF_WALLTIME',
            message='The calculation stopped prematurely because it ran out of walltime.')
        spec.exit_code(410, 'ERROR_CONVERGENCE_NOT_REACHED',
            message='The minimization cycle did not reach self-consistency.')
        # yapf: enable

    def prepare_for_submission(self, folder):
        """Prepare the calculation job for submission by transforming input nodes into input files.

        In addition to the input files being written to the sandbox folder, a `CalcInfo` instance will be returned that
        contains lists of files that need to be copied to the remote machine before job submission, as well as file
        lists that are to be retrieved after job completion.

        :param folder: a sandbox folder to temporarily write files on disk.
        :return: :py:class:`~aiida.common.datastructures.CalcInfo` instance.
        """
        # pylint: disable=too-many-statements,too-many-branches
        local_copy_list = []
        remote_symlink_list = []
        remote_copy_list = []

        settings = self.inputs.settings.get_dict()

        parent_folder = self.inputs.parent_folder
        parent_calcs = parent_folder.get_incoming(
            node_class=orm.CalcJobNode
        ).all()

        if not parent_calcs:
            raise exceptions.NotExistent(
                f"parent_folder<{parent_folder.pk}> has no parent calculation"
            )
        elif len(parent_calcs) > 1:
            raise exceptions.UniquenessError(
                f"parent_folder<{parent_folder.pk}> has multiple parent calculations"
            )

        parent_calc = parent_calcs[0].node
        parent_class = parent_calc.process_class

        if parent_calc.process_type != "aiida.calculations:quantumespresso.ph":
            raise exceptions.InputValidationError(
                "Parent Calculation is not a ph calculation."
            )

        parameters = parent_calc.inputs.parameters.get_dict()
        INPUTPH = parameters.get("INPUTPH", None)
        if not INPUTPH:
            raise exceptions.NotExistent(
                "Cannot get `INPUTPH` from parameters of the parent ph calculation."
            )
        parameters["INPUTPH"].pop("start_q", None)
        parameters["INPUTPH"].pop("last_q", None)
        parameters["INPUTPH"]["recover"] = True
        parameters["INPUTPH"]["fildvscf"] = self._DVSCF_PREFIX
        parameters["INPUTPH"]["verbosity"] = self._VERBOSITY
        # [PorYoung] recover to get dyn.xml
        parameters["INPUTPH"]["fildyn"] = os.path.join(
            parent_class._FOLDER_DYNAMICAL_MATRIX,
            f"{self._PREFIX}.dyn.xml",
        )

        if "settings" in parent_calc.inputs:
            ph_settings = parent_calc.inputs.settings.get_dict()
            settings = ph_settings.update(settings)

        # If the parent calculation is a `PhCalculation` we are restarting
        restart_flag = True

        # Also, the parent calculation must be on the same computer
        if not self.node.computer.uuid == parent_calc.computer.uuid:
            raise exceptions.InputValidationError(
                "Calculation has to be launched on the same computer as that of the parent: {}".format(
                    parent_calc.computer.get_name()
                )
            )

        # put by default, default_parent_output_folder = ./out
        try:
            default_parent_output_folder = (
                parent_class._OUTPUT_SUBFOLDER
            )  # pylint: disable=protected-access
        except AttributeError:
            try:
                default_parent_output_folder = (
                    parent_calc._get_output_folder()
                )  # pylint: disable=protected-access
            except AttributeError as exception:
                msg = "parent calculation does not have a default output subfolder"
                raise exceptions.InputValidationError(msg) from exception
        parent_calc_out_subfolder = settings.pop(
            "PARENT_CALC_OUT_SUBFOLDER", default_parent_output_folder
        )

        parameters["INPUTPH"]["outdir"] = parent_class._OUTPUT_SUBFOLDER
        parameters["INPUTPH"]["prefix"] = parent_class._PREFIX

        try:
            mesh, offset = parent_calc.inputs.qpoints.get_kpoints_mesh()

            if any([i != 0.0 for i in offset]):
                raise NotImplementedError(
                    "Computation of phonons on a mesh with non zero offset is not implemented, at the level of ph.x"
                )

            parameters["INPUTPH"]["ldisp"] = True
            parameters["INPUTPH"]["nq1"] = mesh[0]
            parameters["INPUTPH"]["nq2"] = mesh[1]
            parameters["INPUTPH"]["nq3"] = mesh[2]

            postpend_text = None

        except AttributeError:
            # this is the case where no mesh was set. Maybe it's a list
            try:
                list_of_points = parent_calc.inputs.qpoints.get_kpoints(
                    cartesian=True
                )
            except AttributeError as exception:
                # In this case, there are no info on the qpoints at all
                msg = "Input `qpoints` contains neither a mesh nor a list of points"
                raise exceptions.InputValidationError(msg) from exception

            # change to 2pi/a coordinates
            lattice_parameter = numpy.linalg.norm(
                parent_calc.inputs.qpoints.cell[0]
            )
            list_of_points *= lattice_parameter / (2.0 * numpy.pi)

            # add here the list of point coordinates
            if len(list_of_points) > 1:
                parameters["INPUTPH"]["qplot"] = True
                parameters["INPUTPH"]["ldisp"] = True
                postpend_text = f"{len(list_of_points)}\n"
                for points in list_of_points:
                    postpend_text += (
                        "{0:18.10f} {1:18.10f} {2:18.10f}  1\n".format(*points)
                    )

                # Note: the weight is fixed to 1, because ph.x calls these
                # things weights but they are not such. If they are going to
                # exist with the meaning of weights, they will be supported
            else:
                parameters["INPUTPH"]["ldisp"] = False
                postpend_text = ""
                for points in list_of_points:
                    postpend_text += (
                        "{0:18.10f} {1:18.10f} {2:18.10f}\n".format(*points)
                    )

        # customized namelists, otherwise not present in the distributed ph code
        try:
            namelists_toprint = settings.pop("NAMELISTS")
            if not isinstance(namelists_toprint, list):
                raise exceptions.InputValidationError(
                    "The 'NAMELISTS' value, if specified in the settings input "
                    "node, must be a list of strings"
                )
        except KeyError:  # list of namelists not specified in the settings; do automatic detection
            namelists_toprint = parent_class._compulsory_namelists

        with folder.open(self.metadata.options.input_filename, "w") as infile:
            for namelist_name in namelists_toprint:
                infile.write(f"&{namelist_name}\n")
                # namelist content; set to {} if not present, so that we leave an empty namelist
                namelist = parameters.pop(namelist_name, {})
                for key, value in sorted(namelist.items()):
                    infile.write(convert_input_to_namelist_entry(key, value))
                infile.write("/\n")

            # add list of qpoints if required
            if postpend_text is not None:
                infile.write(postpend_text)

        if parameters:
            raise exceptions.InputValidationError(
                "The following namelists are specified in parameters, but are "
                "not valid namelists for the current type of calculation: "
                "{}".format(",".join(list(parameters.keys())))
            )

        # copy the parent scratch
        symlink = settings.pop(
            "PARENT_FOLDER_SYMLINK", self._default_symlink_usage
        )  # a boolean
        if symlink:
            # I create a symlink to each file/folder in the parent ./out
            folder.get_subfolder(parent_class._OUTPUT_SUBFOLDER, create=True)

            remote_symlink_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        parent_calc_out_subfolder,
                        "*",
                    ),
                    parent_class._OUTPUT_SUBFOLDER,
                )
            )

            # I also create a symlink for the ./pseudo folder
            # Remove this when the recover option of QE will be fixed (bug when trying to find pseudo file)
            remote_symlink_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        parent_class._get_pseudo_folder(),
                    ),
                    parent_class._get_pseudo_folder(),
                )
            )
        else:
            # here I copy the whole folder ./out
            remote_copy_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        parent_calc_out_subfolder,
                    ),
                    parent_class._OUTPUT_SUBFOLDER,
                )
            )
            # I also copy the ./pseudo folder
            # Remove this when the recover option of QE will be fixed (bug when trying to find pseudo file)
            remote_copy_list.append(
                (
                    parent_folder.computer.uuid,
                    os.path.join(
                        parent_folder.get_remote_path(),
                        parent_class._get_pseudo_folder(),
                    ),
                    parent_class._get_pseudo_folder(),
                )
            )

        if (
            restart_flag
        ):  # in this case, copy in addition also the dynamical matrices
            if symlink:
                remote_symlink_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            parent_class._FOLDER_DYNAMICAL_MATRIX,
                        ),
                        parent_class._FOLDER_DYNAMICAL_MATRIX,
                    )
                )

            else:
                # copy the dynamical matrices
                # no need to copy the _ph0, since I copied already the whole ./out folder
                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            parent_class._FOLDER_DYNAMICAL_MATRIX,
                        ),
                        ".",
                    )
                )

        # Create an `.EXIT` file if `only_initialization` flag in `settings` is set to `True`
        if settings.pop("ONLY_INITIALIZATION", False):
            with folder.open(f"{parent_class._PREFIX}.EXIT", "w") as handle:
                handle.write("\n")

                remote_copy_list.append(
                    (
                        parent_folder.computer.uuid,
                        os.path.join(
                            parent_folder.get_remote_path(),
                            parent_class._FOLDER_DYNAMICAL_MATRIX,
                        ),
                        ".",
                    )
                )

        codeinfo = datastructures.CodeInfo()
        codeinfo.cmdline_params = list(settings.pop("CMDLINE", [])) + [
            "-in",
            self.metadata.options.input_filename,
        ]
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.code_uuid = parent_calc.inputs.code.uuid

        calcinfo = datastructures.CalcInfo()
        calcinfo.uuid = str(self.uuid)
        calcinfo.codes_info = [codeinfo]
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.remote_symlink_list = remote_symlink_list

        # Retrieve by default the output file and the xml file
        filepath_xml_tensor = os.path.join(
            parent_class._OUTPUT_SUBFOLDER,
            "_ph0",
            f"{parent_class._PREFIX}.phsave",
        )
        calcinfo.retrieve_list = []
        calcinfo.retrieve_list.append(self.metadata.options.output_filename)
        calcinfo.retrieve_list.append(parent_class._FOLDER_DYNAMICAL_MATRIX)
        calcinfo.retrieve_list.append(
            os.path.join(
                filepath_xml_tensor, parent_class._OUTPUT_XML_TENSOR_FILE_NAME
            )
        )
        calcinfo.retrieve_list += settings.pop("ADDITIONAL_RETRIEVE_LIST", [])

        if settings:
            unknown_keys = ", ".join(list(settings.keys()))
            raise exceptions.InputValidationError(
                f"`settings` contained unexpected keys: {unknown_keys}"
            )

        return calcinfo