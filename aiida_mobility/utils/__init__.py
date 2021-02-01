from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida_quantumespresso.calculations.functions.create_kpoints_from_distance import (
    create_kpoints_from_distance,
)
from ase.io import read as aseread


def read_structure(structure_file):
    structure = orm.StructureData(ase=aseread(structure_file))
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


def create_kpoints(structure, distance, set_2d_mesh):
    inputs = {
        "structure": structure,
        "distance": orm.Float(distance),
        "force_parity": orm.Bool(False),
        "metadata": {"call_link_label": "create_kpoints_from_distance"},
    }
    kpoints = create_kpoints_from_distance(**inputs)

    if set_2d_mesh:
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