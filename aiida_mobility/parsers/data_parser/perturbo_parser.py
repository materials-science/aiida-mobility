from aiida.common import AIIDA_LOGGER
from aiida.common import exceptions
import numpy as np


class PerturboParser(object):
    """PerturboParser Generates a PerturboParser instance .

    Args:
        object ([type]): [description]

    Raises:
        exceptions.InputValidationError: [description]
        exceptions.InputValidationError: [description]

    TODO: verify parameters of diffrent calc modes.
    """

    _blocked_keys = [
        "prefix",
        "boltz_kdim(1)",
        "boltz_kdim(2)",
        "boltz_kdim(3)",
        "ftemper",
        "fklist",
        "fqlist",
    ]
    _default_parameters = {"prefix": "aiida", "ftemper": "aiida.temper"}

    def __init__(self, calc_mode="setup", **args):
        """__init__ Initialize the PerturboParser.

        Args:
            calc_mode (str, optional): [description]. Defaults to "setup".
        """
        self._logger = AIIDA_LOGGER.getChild(self.__class__.__name__)
        self.calc_mode = calc_mode.lower()
        self.kpoints = args.pop("kpoints", None)
        self.parameters = args
        self._validate_input()

    def _validate_input(self):
        parameters = self.parameters
        for key in self._blocked_keys:
            if key in parameters:
                raise exceptions.InputValidationError(
                    f"key `{key}` is not allowed."
                )

        # get mesh or kpt
        if self.kpoints is not None:
            formated = self._format_kpoints(self.kpoints)
            if self.calc_mode == "setup":
                mesh = formated[0]
                parameters["boltz_kdim(1)"] = mesh[0]
                parameters["boltz_kdim(2)"] = mesh[1]
                parameters["boltz_kdim(3)"] = mesh[2]
            else:
                pass

        if self.calc_mode in ["imsigma", "meanfp"]:
            parameters[
                "fklist"
            ] = f"{self._default_parameters.get('prefix')}_tet.kpt"
            if "sampling" not in parameters:
                parameters["fqlist"] = parameters["fklist"]

        self.valid_control = parameters
        self.valid_control.update(self._default_parameters)

    def write(self, dist):
        try:
            self.valid_control
        except AttributeError:
            self._logger.error("Valid variable `control` does not exist.")
            raise exceptions.InputValidationError("INVALID_CONTROL")
        with open(dist, "w", encoding="utf8") as target:
            target.write("&perturbo\n")
            for key, val in self.valid_control.items():
                if isinstance(val, bool):
                    target.write(f'\t{key}={".true." if val else ".false."},\n')
                elif isinstance(val, str):
                    target.write(f'\t{key}="{val}",\n')
                else:
                    target.write(f"\t{key}={val},\n")
            target.write("/\n")

    def _format_kpoints(kpoints):
        try:
            has_mesh = True
            mesh, offset = kpoints.get_kpoints_mesh()
        except AttributeError as exception:
            try:
                # KpointsData was set with set_kpoints
                kpoints_list = kpoints.get_kpoints()
                num_kpoints = len(kpoints_list)
                has_mesh = False
                if num_kpoints == 0:
                    raise exceptions.InputValidationError(
                        "At least one k point must be provided for non-gamma calculations"
                    )
            except AttributeError:
                raise exceptions.InputValidationError(
                    "No valid kpoints have been found"
                ) from exception

            try:
                _, weights = kpoints.get_kpoints(also_weights=True)
            except AttributeError:
                weights = [1.0] * num_kpoints

        if has_mesh:
            return mesh, offset
        else:
            kpoints_card_list = []
            kpoints_card_list.append(f"{num_kpoints:d}\n")
            for kpoint, weight in zip(kpoints_list, weights):
                kpoints_card_list.append(
                    f"  {kpoint[0]:18.10f} {kpoint[1]:18.10f} {kpoint[2]:18.10f} {weight:18.10f}\n"
                )
            return "".join(kpoints_card_list)
