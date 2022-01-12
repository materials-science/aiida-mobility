import argparse
from aiida import orm
from aiida.common import exceptions
from aiida.common.exceptions import NotExistent
from aiida.common.extendeddicts import AttributeDict
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from aiida_quantumespresso.utils.pseudopotential import get_pseudos_from_dict
import numpy as np
from aiida_mobility.utils.protocols.pw import ProtocolManager
from ase.io import read as aseread


def get_calc_from_folder(folder):
    parent_calcs = folder.get_incoming(
        node_class=orm.CalcJobNode
    ).all()

    if not parent_calcs:
        raise exceptions.NotExistent(
            f"folder<{folder.pk}> has no parent calculation"
        )
    elif len(parent_calcs) > 1:
        raise exceptions.UniquenessError(
            f"folder<{folder.pk}> has multiple parent calculations"
        )

    parent_calc = parent_calcs[0].node
    return parent_calc

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


def create_kpoints(structure, distance, system_2d=False, force_parity=False):
    inputs = {
        "structure": structure,
        "distance": orm.Float(distance),
        "force_parity": orm.Bool(force_parity),
        "metadata": {"call_link_label": "create_kpoints_from_distance"},
    }
    kpoints = create_kpoints_from_distance(**inputs)

    cells = structure.cell_lengths/max(structure.cell_lengths)
    cindex = tuple(np.where(np.isclose(cells, 1)==True)[0])

    if system_2d:
        kpoints = kpoints.clone()
        mesh = kpoints.get_kpoints_mesh()
        if len(cindex) == 1:
            mesh[0][cindex[0]] = 1
        else:
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


def input_pw_parameters_helper(mode, inputs, version='6.5'):
    # TODO: Add ALL Parameters for all versions
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
        "input_dft",
        "lspinorb",
        "noncolin",
        "ibrav",
    ]
    _electron = [
        "conv_thr",
        "mixing_beta",
        "mixing_ndim",
        "mixing_mode",
        "electron_maxstep",
        "scf_must_converge",
        "diago_full_acc",
        "diagonalization",
    ]
    _ions = ["trust_radius_min"]
    _cell = ["press", "press_conv_thr", "cell_dofree"]
    con = {}
    sys = {}
    ele = {}
    ions = {}
    cell = {}
    flat_dict = {}
    for (key, val) in inputs.items():
        if key in ["CONTROL", "SYSTEM", "ELECTRONS", "CELL", "IONS"] and isinstance(val, dict):
            flat_dict.update(val)
        elif key not in flat_dict.keys(): # avoid overrideing
            flat_dict[key] = val
    for (key, val) in flat_dict.items():
        if key in _control:
            con[key] = val
        elif key in _system:
            sys[key] = val
        elif key in _electron:
            ele[key] = val
        elif key in _ions:
            ions[key] = val
        elif key in _cell and (mode == "vc-relax" or mode == "vc-md"):
            cell[key] = val
        # else:
        #     raise SystemError('Error: Invalid Input Parameters In input_helper ', key)
    parameters = {}
    if con:
        parameters["CONTROL"] = con
    if sys:
        parameters["SYSTEM"] = sys
    if ele:
        parameters["ELECTRONS"] = ele
    if ions:
        parameters["IONS"] = ions
    if cell or (mode == "vc-relax" or mode == "vc-md"):
        parameters["CELL"] = cell

    return parameters


def get_protocol(structure, scf_parameters_name, protocol, pseudos=None):
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
    num_machines, num_mpiprocs_per_machine, walltime=5*3600, queue_name=None
):
    options = {
        "resources": {
            "num_machines": num_machines,
            "num_mpiprocs_per_machine": num_mpiprocs_per_machine,
        },
        "max_wallclock_seconds": walltime,
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
    walltime=5*3600,
    queue_name=None,
    kpoints=None
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
    pw_parameters = input_pw_parameters_helper(mode, prepare_for_parameters)
    inputs = AttributeDict(
        {
            "pw": {
                "code": pw_code if isinstance(pw_code, orm.Code) else orm.load_code(pw_code),
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

    if kpoints is not None:
        inputs["kpoints"] = kpoints

    inputs.pw.metadata.options = get_metadata_options(
        num_machines,
        num_mpiprocs_per_machine,
        walltime=walltime,
        queue_name=queue_name,
    )

    return inputs


class StoreDictKeyPair(argparse.Action):
     def __init__(self, option_strings, dest, nargs=None, **kwargs):
         self._nargs = nargs
         super(StoreDictKeyPair, self).__init__(option_strings, dest, nargs=nargs, **kwargs)
     def __call__(self, parser, namespace, values, option_string=None):
         my_dict = {}
         for kv in values:
             k,v = kv.split("=")
             if v in ["True", "true"]:
                my_dict[k] = True
             elif v in ["False", "false"]:
                my_dict[k] = False
             else:
                try:
                    my_dict[k] = int(v)
                except ValueError:
                    try:
                        my_dict[k] = float(v)
                    except ValueError:
                        my_dict[k] = v
         setattr(namespace, self.dest, my_dict)