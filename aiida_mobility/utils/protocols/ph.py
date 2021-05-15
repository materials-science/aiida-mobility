_protocol = {
    "ms-1.0": {
        "parameters": {
            "test": {
                "tr2_ph": 1e-6,
                "qpoints_distance": 0.6,
                "max_wallclock_seconds": 3600 * 60,
                "check_imaginary_frequencies": False,
                "epsil": False,
                "separated_qpoints": False,
                "frequency_threshold": -50,
                "zasr": "no",
                "asr": "no",
                "matdyn_distance": 0.01,
            },
            "default_crystal": {
                "tr2_ph": 1e-15,
                "qpoints_distance": 0.5,
                "max_wallclock_seconds": 3600 * 60 * 24,
                "check_imaginary_frequencies": True,
                "epsil": False,
                "separated_qpoints": False,
                "frequency_threshold": -30,
                "zasr": "crystal",
                "asr": "crystal",
                "matdyn_distance": 0.01,
            },
            "accurate_crystal": {
                "tr2_ph": 1e-17,
                "qpoints_distance": 0.4,
                "max_wallclock_seconds": 3600 * 60 * 72,
                "check_imaginary_frequencies": True,
                "epsil": False,
                "separated_qpoints": False,
                "frequency_threshold": -20,
                "zasr": "crystal",
                "asr": "crystal",
                "matdyn_distance": 0.005,
            },
            "accurate_crystal_elph": {
                "tr2_ph": 1e-17,
                "qpoints_distance": 0.4,
                "max_wallclock_seconds": 3600 * 60 * 72,
                "check_imaginary_frequencies": True,
                "epsil": True,
                "separated_qpoints": False,
                "frequency_threshold": -20,
                "zasr": "crystal",
                "asr": "crystal",
                "matdyn_distance": 0.005,
            },
        },
        "parameters_default": "default_crystal",
    }
}


def get_ph_protocol_parameters(name="ms-1.0", type=None):
    return _protocol[name]["parameters"][
        _protocol[name]["parameters_default"] if type is None else type
    ]


def _get_all_protocol_modifiers():
    return _protocol