# -*- coding: utf-8 -*-
"""Protocol definitions for workflow input generation."""
import json
import os
from copy import deepcopy


def _load_pseudo_metadata(filename):
    """Load from the current folder a json file containing metadata (incl.

    suggested cutoffs) for a library of pseudopotentials.
    """
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    ) as handle:
        return json.load(handle)


def _get_all_protocol_modifiers():
    """Return the information on all possibile modifiers for all known protocols.

    It is a function so we can lazily load the jsons.
    """
    protocols = {
        "theos-ht-1.0": {
            "pseudo": {
                # SSSP Efficiency & Precision v1.0, see https://www.materialscloud.org/archive/2018.0001/v2
                "SSSP-efficiency-1.0": _load_pseudo_metadata(
                    "sssp_efficiency_1.0.json"
                ),
                "SSSP-precision-1.0": _load_pseudo_metadata(
                    "sssp_precision_1.0.json"
                ),
                # SSSP Efficiency & Precision v1.1, see https://www.materialscloud.org/archive/2018.0001/v3
                "SSSP-efficiency-1.1": _load_pseudo_metadata(
                    "sssp_efficiency_1.1.json"
                ),
                "SSSP-precision-1.1": _load_pseudo_metadata(
                    "sssp_precision_1.1.json"
                ),
            },
            "pseudo_default": "SSSP-efficiency-1.1",
            "parameters": {
                "fast": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.3,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 2.0e-06,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": False,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "fast_gaussian": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.3,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 2.0e-06,
                    "smearing": "gaussian",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": False,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "default": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "default_fixed": {
                    "occupations": "fixed",
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "default_gaussian": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "smearing": "gaussian",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
            },
            "parameters_default": "default",
        },
        "ms-1.0": {
            "pseudo": {
                "SSSP-efficiency-1.0": _load_pseudo_metadata(
                    "sssp_efficiency_1.0.json"
                ),
                "SSSP-precision-1.0": _load_pseudo_metadata(
                    "sssp_precision_1.0.json"
                ),
                "SSSP-efficiency-1.1": _load_pseudo_metadata(
                    "sssp_efficiency_1.1.json"
                ),
                "SSSP-precision-1.1": _load_pseudo_metadata(
                    "sssp_precision_1.1.json"
                ),
            },
            "pseudo_default": "SSSP-efficiency-1.1",
            "parameters": {
                "default": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "default_td": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    # "electron_maxstep": 200,
                    # "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                },
                "default_td_soc": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    # "electron_maxstep": 200,
                    # "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "accurate_default": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "diagonalization": "cg",
                },
                "accurate_default_soc": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "diagonalization": "cg",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "accurate_default_td": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "diagonalization": "cg",
                },
                "accurate_default_td_soc": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "marzari-vanderbilt",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "diagonalization": "cg",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "accurate_gaussian": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "gaussian",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "diagonalization": "cg",
                },
                "accurate_gaussian_td": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "gaussian",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "diagonalization": "cg",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "accurate_gaussian_td_soc": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "smearing": "gaussian",
                    "degauss": 0.02,
                    "occupations": "smearing",
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "nstep": 400,
                    "num_bands_factor": 3,
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "diagonalization": "cg",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "default_fixed": {
                    "occupations": "fixed",
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.3,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                },
                "accurate_fixed": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "occupations": "fixed",
                    # increase if error occurred
                    "nstep": 400,
                    "num_bands_factor": 3,  # number of bands wrt number of occupied bands
                    "diagonalization": "cg",
                },
                "fast_fixed_td": {
                    "occupations": "fixed",
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.4,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 1.0e-6,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    # "vdw_corr": "DFT-D",
                },
                "default_fixed_td": {
                    "occupations": "fixed",
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.3,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    # "vdw_corr": "DFT-D",
                },
                "default_fixed_td": {
                    "occupations": "fixed",
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.3,
                    "kpoints_distance_for_bands": 0.02,
                    "convergence_threshold_per_atom": 1.0e-10,
                    "forc_conv_thr": 1.0e-3,
                    "etot_conv_thr": 1.0e-4,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "num_bands_factor": None,  # number of bands wrt number of occupied bands
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    # "vdw_corr": "DFT-D",
                    "lspinorb": True,
                    "noncolin": True,
                },
                "accurate_fixed_td": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "occupations": "fixed",
                    # increase if error occurred
                    "nstep": 400,
                    "num_bands_factor": 3,  # number of bands wrt number of occupied bands
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    "diagonalization": "cg",
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                },
                "accurate_fixed_td_soc": {
                    "kpoints_mesh_offset": [0.0, 0.0, 0.0],
                    "kpoints_mesh_density": 0.2,
                    "kpoints_distance_for_bands": 0.01,
                    "convergence_threshold_per_atom": 1.0e-12,
                    "forc_conv_thr": 1.0e-8,
                    "etot_conv_thr": 1.0e-8,
                    "press_conv_thr": 0.5,
                    "meta_convergence": True,
                    "volume_convergence": 0.01,
                    "tstress": True,
                    "tprnfor": True,
                    "occupations": "fixed",
                    # increase if error occurred
                    "nstep": 400,
                    "num_bands_factor": 3,  # number of bands wrt number of occupied bands
                    "assume_isolated": "2D",
                    "cell_dofree": "2Dxy",
                    "electron_maxstep": 200,
                    "diago_full_acc": True,
                    "diagonalization": "cg",
                    # "mixing_mode": "local-TF",
                    # "mixing_beta": 0.7,
                    # "vdw_corr": "DFT-D",
                    "lspinorb": True,
                    "noncolin": True,
                },
            },
            "parameters_default": "accurate_default",
        },
    }
    protocols["theos-ht-1.0"]["parameters"]["scdm"] = deepcopy(
        protocols["theos-ht-1.0"]["parameters"]["default"]
    )
    protocols["theos-ht-1.0"]["parameters"]["scdm"]["num_bands_factor"] = 3.0

    protocols["ms-1.0"]["parameters"]["scdm"] = deepcopy(
        protocols["ms-1.0"]["parameters"]["default"]
    )
    protocols["ms-1.0"]["parameters"]["scdm"]["num_bands_factor"] = 3.0

    # a protocol for testing purpose, decrease kmesh density & ecutoff
    testing = deepcopy(protocols["theos-ht-1.0"])
    testing["parameters"]["fast"]["kpoints_mesh_density"] = 0.3
    testing["parameters_default"] = "fast"
    ps_data = testing["pseudo"]["SSSP-efficiency-1.1"]
    for pseudo in ps_data:
        ps_data[pseudo]["cutoff"] = ps_data[pseudo]["cutoff"] / 2
    testing["pseudo"]["SSSP-efficiency-1.1"] = ps_data
    protocols["testing"] = testing

    return protocols


class ProtocolManager:
    """A class to manage calculation protocols."""

    def __init__(self, name):
        """Initialize a protocol instance.

        Pass a string specifying the protocol.
        """
        self.name = name
        try:
            self.modifiers = _get_all_protocol_modifiers()[name]
        except KeyError as exception:
            raise ValueError(f"Unknown protocol '{name}'") from exception

    def get_protocol_data(self, modifiers=None):
        """Return the full info on the specific protocol, using the (optional) modifiers.

        :param modifiers: should be a dictionary with (optional) keys 'parameters' and 'pseudo', and
          whose value is the modifier name for that category.
          If the key-value pair is not specified, the default for the protocol will be used.
          In this case, if no default is specified, a ValueError is thrown.

        .. note:: If you pass 'custom' as the modifier name for 'pseudo',
          then you have to pass an additional key, called 'pseudo_data', that will be
          used to populate the output.
        """
        if modifiers is None:
            modifiers = {}

        modifiers_copy = modifiers.copy()
        parameters_modifier_name = modifiers_copy.pop(
            "parameters", self.get_default_parameters_modifier_name()
        )
        pseudo_modifier_name = modifiers_copy.pop(
            "pseudo", self.get_default_pseudo_modifier_name()
        )

        if parameters_modifier_name is None:
            raise ValueError(
                "You did not specify a modifier name for 'parameters', but no default "
                "modifier name exists for protocol '{}'.".format(self.name)
            )
        if pseudo_modifier_name is None:
            raise ValueError(
                "You did not specify a modifier name for 'pseudo', but no default "
                "modifier name exists for protocol '{}'.".format(self.name)
            )

        if pseudo_modifier_name == "custom":
            try:
                pseudo_data = modifiers_copy.pop("pseudo_data")
            except KeyError as exception:
                raise ValueError(
                    "You specified 'custom' as a modifier name for 'pseudo', but you did not provide "
                    "a 'pseudo_data' key."
                ) from exception
        else:
            pseudo_data = self.get_pseudo_data(pseudo_modifier_name)

        # Check that there are no unknown modifiers
        if modifiers_copy:
            raise ValueError(
                f"Unknown modifiers specified: {','.join(sorted(modifiers_copy))}"
            )

        retdata = self.get_parameters_data(parameters_modifier_name)
        retdata["pseudo_data"] = pseudo_data

        return retdata

    def get_parameters_modifier_names(self):
        """Get all valid parameters modifier names."""
        return list(self.modifiers["parameters"].keys())

    def get_default_parameters_modifier_name(
        self,
    ):  # pylint: disable=invalid-name
        """Return the default parameter modifier name (or None if no default is specified)."""
        return self.modifiers.get("parameters_default", None)

    def get_parameters_data(self, modifier_name):
        """Given a parameter modifier name, return a dictionary of data associated to it."""
        return self.modifiers["parameters"][modifier_name]

    def get_pseudo_modifier_names(self):
        """Get all valid pseudopotential modifier names."""
        return list(self.modifiers["pseudo"].keys())

    def get_default_pseudo_modifier_name(self):  # pylint: disable=invalid-name
        """Return the default pseudopotential modifier name (or None if no default is specified)."""
        return self.modifiers.get("pseudo_default", None)

    def get_pseudo_data(self, modifier_name):
        """Given a pseudo modifier name, return the ``pseudo_data`` associated to it."""
        return self.modifiers["pseudo"][modifier_name]

    def check_pseudos(self, modifier_name=None, pseudo_data=None):
        """Given a pseudo modifier name, checks which pseudos exist in the DB.

        :param modifier_name: the name of the modifier. Leave to None to use the default one.
        :param pseudo_data: should be passed only if modifier_name == 'custom'

        :return: a dictionary with three keys:

            - ``missing``: a set of element names that are not in the DB
            - ``found``: a dictionary with key-value: ``{element_name: uuid}`` for the pseudos that were found
            - ``mismatch``: a dictionary with key-value: ``{element_name: [list-of-elements-found]}`` for those
              pseudos for which one (or more) pseudos were found with the same MD5, but associated to different elements
              (listed in `list-of-elements-found`)
        """
        from aiida.orm import QueryBuilder
        from aiida.plugins import DataFactory

        UpfData = DataFactory("upf")

        if modifier_name is None:
            modifier_name = self.get_default_pseudo_modifier_name()
        if modifier_name is None:
            raise ValueError(
                "You did not specify a modifier name, but no default "
                "modifier name exists for protocol '{}'.".format(self.name)
            )

        if modifier_name == "custom":
            if pseudo_data is None:
                raise ValueError(
                    "You chose 'custom' as modifier_name, but did not provide a "
                    "pseudo_data!"
                )
        else:
            if pseudo_data is not None:
                raise ValueError(
                    "You passed a pseudo_data, but the modifier name is not 'custom'!"
                )
            pseudo_data = self.get_pseudo_data(modifier_name)

        # No pseudo found
        missing = set()
        # Pseudo found and ok
        found = {}
        # Pseudo with MD5 found, but wrong element!
        mismatch = {}

        for element, this_pseudo_data in pseudo_data.items():
            md5 = this_pseudo_data["md5"]

            builder = QueryBuilder()
            builder.append(
                UpfData,
                filters={"attributes.md5": md5},
                project=["uuid", "attributes.element"],
            )
            res = builder.all()
            if len(res) >= 1:
                this_mismatch_elements = []
                for this_uuid, this_element in res:
                    if element == this_element:
                        found[element] = this_uuid
                        break

                    this_mismatch_elements.append(this_element)
                if element not in found:
                    mismatch[element] = this_mismatch_elements
            else:
                missing.add(element)

        return {"missing": missing, "found": found, "mismatch": mismatch}


if __name__ == "__main__":
    MANAGER = ProtocolManager("theos-ht-1.0")
    print(MANAGER.check_pseudos())
    print(MANAGER.get_protocol_data())
