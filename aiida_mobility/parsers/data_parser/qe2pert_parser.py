from aiida.common import AIIDA_LOGGER
from aiida.common.exceptions import InputValidationError, NotExistentKeyError
import numpy as np


class QE2pertParser(object):
    _key = [
        "prefix",
        "outdir",
        "phdir",
        "nk1",
        "nk2",
        "nk3",
        "dft_band_min",
        "dft_band_max",
        "num_wann",
        "lwannier",
        "load_ephmat",
        "system_2d",
    ]

    def __init__(self, **args):
        """
        param: prefix
        param: outdir
        param: phdir
        param: kpoints
        param: dft_band_min
        param: dft_band_max
        param: num_wann
        param: lwannier
        param: system_2d
        """
        self._logger = AIIDA_LOGGER.getChild(self.__class__.__name__)
        params = args
        kpoints = params.pop("kpoints")
        mesh, offset = kpoints.get_kpoints_mesh()
        params["nk1"] = mesh[0]
        params["nk2"] = mesh[1]
        params["nk3"] = mesh[2]
        params.setdefault("load_ephmat", False)

        self.parameters = params
        self._validate_input()

    def _validate_input(self):
        valid_paremeters = {}

        for key, inner in self.parameters.items():
            if key not in self._key:
                self._logger.error(f"key `{key}` is not valid")
                raise InputValidationError("ERROR_KEY_IN_INPUT")
            valid_paremeters[key] = self.parameters[key]

        # arrange in order
        # ? only available in python version>=3.6
        valid_dict = {}
        for key in self._key:
            if key not in valid_paremeters:
                self._logger.error(f"key `{key}` is not in given parameters.")
                raise InputValidationError("ERROR_KEY_IN_INPUT")
            valid_dict[key] = valid_paremeters[key]

        self.valid_control = valid_dict

    def write(self, dist):
        try:
            self.valid_control
        except AttributeError:
            self._logger.error("Valid variable `control` does not exist.")
            raise InputValidationError("INVALID_CONTROL")
        with open(dist, "w", encoding="utf8") as target:
            target.write("&qe2pert\n")
            for key, val in self.valid_control.items():
                if isinstance(val, bool):
                    target.write(f'\t{key}={".true." if val else ".false."},\n')
                elif isinstance(val, str):
                    target.write(f'\t{key}="{val}",\n')
                else:
                    target.write(f"\t{key}={val},\n")
            target.write("/\n")