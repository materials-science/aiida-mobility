from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.common.extendeddicts import AttributeDict
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_dict
from aiida_mobility.utils.protocols.pw import ProtocolManager
from ase.io import read as aseread


def read_structure(structure_file, store=False):
    structure = orm.StructureData(ase=aseread(structure_file))
    if store is True:
        structure.store()
    print(
        "Structure {} read and stored with pk {}.".format(
            structure.get_formula(), structure.pk
        )
    )
    return structure


def add_to_group(node, group_name):
    if group_name is not None:
        try:
            g = orm.Group.get(label=group_name)
            group_statistics = "that already contains {} nodes".format(
                len(g.nodes)
            )
        except NotExistent:
            g = orm.Group(label=group_name)
            group_statistics = "that does not exist yet"
            g.store()
        g.add_nodes(node)
        print(
            "Node<{}> will be added to the group {} {}".format(
                node.pk, group_name, group_statistics
            )
        )


def print_help(workchain, structure=None):
    if structure is None:
        print("launched WorkChain pk {}.".format(workchain.pk))
    else:
        print(
            "launched WorkChain pk {} for structure {}".format(
                workchain.pk, structure.get_formula()
            )
        )
    print("")
    print("# To get a detailed state of the workflow, run:")
    print("verdi process report {}".format(workchain.pk))


def write_pk_to_file(workchain, structure=None, ext=""):
    import os

    dir = "." if structure is None else "{}".format(structure.get_formula())
    if not os.path.isdir(dir):
        os.mkdir(dir)
    with open("{}/{}.{}".format(dir, workchain.pk, ext), "w") as f:
        f.write("verdi process report {}".format(workchain.pk))


def create_kpoints(structure, distance, system_2d):
    inputs = {
        "structure": structure,
        "distance": orm.Float(distance),
        "force_parity": orm.Bool(False),
        "metadata": {"call_link_label": "create_kpoints_from_distance"},
    }
    kpoints = create_kpoints_from_distance(**inputs)

    if system_2d:
        kpoints = kpoints.clone()
        mesh = kpoints.get_kpoints_mesh()
        mesh[0][2] = 1
        kpoints.set_kpoints_mesh(mesh[0])
    return kpoints


def constr2dpath(kpath3d, **kpath3ddict):
    kpath = []
    labels = []
    label_numbers = []
    labels3d = kpath3ddict["labels"]
    label_numbers3d = kpath3ddict["label_numbers"]
    i2d = 0
    for i in range(len(kpath3d)):
        if abs(kpath3d[i][2]) < 0.001:
            kpath.append(kpath3d[i])
            if i in label_numbers3d:
                labels.append(labels3d[label_numbers3d.index(i)])
                label_numbers.append(i2d)
            i2d = i2d + 1
    kpathdict = dict({"labels": labels, "label_numbers": label_numbers})

    return kpath, kpathdict


def input_pw_parameters_helper(mode, inputs):
    # TODO: Add ALL Parameters
    _control = [
        "restart_mode",
        "tstress",
        "tprnfor",
        "etot_conv_thr",
        "forc_conv_thr",
        "nstep",
    ]
    _system = [
        "ecutwfc",
        "ecutrho",
        "smearing",
        "degauss",
        "occupations",
        "assume_isolated",
        "vdw_corr",
    ]
    _electron = [
        "conv_thr",
        "mixing_beta",
        "mixing_ndim",
        "mixing_mode",
        "electron_maxstep",
        "scf_must_converge",
        "diago_full_acc",
    ]
    _ions = ["trust_radius_min"]
    _cell = ["press", "press_conv_thr", "cell_dofree"]
    con = {}
    sys = {}
    ele = {}
    ions = {}
    cell = {}
    for key in inputs.keys():
        if key in _control:
            con[key] = inputs[key]
        elif key in _system:
            sys[key] = inputs[key]
        elif key in _electron:
            ele[key] = inputs[key]
        elif key in _ions:
            ions[key] = inputs[key]
        elif key in _cell and (mode == "vc-relax" or mode == "vc-md"):
            cell[key] = inputs[key]
        # else:
        #     raise SystemError('Error: Invalid Input Parameters In input_helper ', key)
    parameters = {}
    if con:
        parameters["CONTROL"] = con
    if sys:
        parameters["SYSTEM"] = sys
    if ele:
        parameters["ELECTRONS"] = ele
    if cell:
        parameters["CELL"] = cell

    return parameters


def get_protocol(structure, scf_parameters_name, protocol, pseudos):
    # get custom pseudo
    modifiers = {"parameters": scf_parameters_name}
    recommended_cutoffs = None
    if pseudos is not None:
        from aiida_quantumespresso.utils.protocols.pw import (
            _load_pseudo_metadata,
        )

        pseudo_json_data = _load_pseudo_metadata(pseudos)
        structure_name = structure.get_formula()
        if structure_name in pseudo_json_data:
            pseudo_dict = pseudo_json_data[structure_name]
            if "pseudo_family" in pseudo_dict:
                pseudo_family = pseudo_dict["pseudo_family"]
                recommended_cutoffs = {
                    "cutoff": pseudo_dict["cutoff"],
                    "dual": pseudo_dict["dual"],
                }
            elif "pseudos" in pseudo_dict:
                pseudo_data = {}
                pseudo_map = pseudo_dict["pseudos"]
                for ele in pseudo_map:
                    pseudo_data[ele] = pseudo_map[ele]
                    pseudo_data[ele].update(
                        {
                            "cutoff": pseudo_dict["cutoff"],
                            "dual": pseudo_dict["dual"],
                        }
                    )
                modifiers.update(
                    {"pseudo": "custom", "pseudo_data": pseudo_data}
                )
            else:
                print(
                    "neither pseudo_family or pseudos is provided in json data"
                )
                exit(1)
        else:
            print(
                "No structure found in json data. Please check your filename."
            )
            exit(1)
    # get protocol
    protocol_manager = ProtocolManager(protocol)
    protocol_modifiers = modifiers
    protocol = protocol_manager.get_protocol_data(modifiers=protocol_modifiers)

    return protocol, recommended_cutoffs


def get_metadata_options(
    num_machines, num_mpiprocs_per_machine, walltime=5, queue_name=None
):
    options = {
        "resources": {
            "num_machines": num_machines,
            "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
        },
        "max_wallclock_seconds": 3600 * walltime,
        "withmpi": True,
    }
    if queue_name is not None:
        options["queue_name"] = queue_name
    return options


def get_pw_common_inputs(
    structure,
    pw_code,
    protocol,
    recommended_cutoffs,
    pseudo_family,
    cutoffs,
    system_2d,
    num_machines,
    num_mpiprocs_per_machine,
    mode="scf",
    walltime=5,
    queue_name=None,
):
    # get cutoff
    ecutwfc = []
    ecutrho = []
    if cutoffs is not None and len(cutoffs) == 2:
        cutoff = cutoffs[0]
        dual = cutoffs[1]
        cutrho = cutoff * dual
        ecutwfc.append(cutoff)
        ecutrho.append(cutrho)
    elif recommended_cutoffs is not None:
        cutoff = recommended_cutoffs["cutoff"]
        dual = recommended_cutoffs["dual"]
        cutrho = cutoff * dual
        ecutwfc.append(cutoff)
        ecutrho.append(cutrho)
    else:
        for kind in structure.get_kind_names():
            try:
                cutoff = protocol["pseudo_data"][kind]["cutoff"]
                dual = protocol["pseudo_data"][kind]["dual"]
                cutrho = dual * cutoff
                ecutwfc.append(cutoff)
                ecutrho.append(cutrho)
            except KeyError:
                raise SystemExit(
                    "failed to retrieve the cutoff or dual factor for {}".format(
                        kind
                    )
                )

    number_of_atoms = len(structure.sites)
    prepare_for_parameters = protocol
    prepare_for_parameters["ecutwfc"] = max(ecutwfc)
    prepare_for_parameters["ecutrho"] = max(ecutrho)
    prepare_for_parameters["conv_thr"] = (
        protocol["convergence_threshold_per_atom"] * number_of_atoms
    )
    # if "smearing" in protocol:
    #     prepare_for_parameters["smearing"] = protocol["smearing"]
    # if "degauss" in protocol:
    #     prepare_for_parameters["degauss"] = protocol["degauss"]
    # if "occupations" in protocol:
    #     prepare_for_parameters["occupations"] = protocol["occupations"]
    pw_parameters = input_pw_parameters_helper(mode, prepare_for_parameters)
    # pw_parameters = {
    #     "CONTROL": {
    #         "restart_mode": "from_scratch",
    #         "tstress": protocol["tstress"],
    #         "tprnfor": protocol["tprnfor"],
    #         "etot_conv_thr": protocol["etot_conv_thr"],
    #         "forc_conv_thr": protocol["forc_conv_thr"],
    #     },
    #     "SYSTEM": {
    #         "ecutwfc": max(ecutwfc),
    #         "ecutrho": max(ecutrho),
    #     },
    #     "ELECTRONS": {
    #         "conv_thr": protocol["convergence_threshold_per_atom"]
    #         * number_of_atoms,
    #     },
    # }

    # if "smearing" in protocol:
    #     pw_parameters["SYSTEM"]["smearing"] = protocol["smearing"]
    # if "degauss" in protocol:
    #     pw_parameters["SYSTEM"]["degauss"] = protocol["degauss"]
    # if "occupations" in protocol:
    #     pw_parameters["SYSTEM"]["occupations"] = protocol["occupations"]

    inputs = AttributeDict(
        {
            "pw": {
                "code": orm.load_code(pw_code),
                "parameters": orm.Dict(dict=pw_parameters),
                "metadata": {},
            },
            # "max_iterations": orm.Int(5),
        }
    )

    if pseudo_family is not None:
        inputs["pseudo_family"] = orm.Str(pseudo_family)
    else:
        checked_pseudos = protocol.check_pseudos(
            modifier_name=protocol.modifiers.get("pseudo", None),
            pseudo_data=protocol.modifiers.get("pseudo_data", None),
        )
        known_pseudos = checked_pseudos["found"]
        inputs.pw["pseudos"] = get_pseudos_from_dict(structure, known_pseudos)
    if system_2d:
        inputs["system_2d"] = orm.Bool(system_2d)

    inputs.kpoints_distance = orm.Float(protocol["kpoints_mesh_density"])

    inputs.pw.metadata.options = get_metadata_options(
        num_machines,
        num_mpiprocs_per_machine,
        walltime=walltime,
        queue_name=queue_name,
    )

    # return scf_parameters
    return inputs
