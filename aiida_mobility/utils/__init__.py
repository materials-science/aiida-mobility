from aiida import orm
from aiida.common.exceptions import NotExistent
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
            group_statistics = "that already contains {} nodes".format(len(g.nodes))
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


def print_help(workchain, structure):
    print(
        "launched WorkChain pk {} for structure {}".format(
            workchain.pk, structure.get_formula()
        )
    )
    print("")
    print("# To get a detailed state of the workflow, run:")
    print("verdi process report {}".format(workchain.pk))


def write_pk_to_file(workchain, structure, ext):
    import os

    dir = "{}".format(structure.get_formula())
    if not os.path.isdir(dir):
        os.mkdir(dir)
    with open("{}/{}.{}".format(dir, workchain.pk, ext), "w") as f:
        f.write("verdi process report {}".format(workchain.pk))
