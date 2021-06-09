#!/usr/bin/env runaiida
from aiida.orm import load_node
import argparse


def get_fermi_energy(scf_output_parameters):
    """get Fermi energy from scf output parameters, unit is eV"""
    try:
        scf_out_dict = scf_output_parameters.get_dict()
        efermi = scf_out_dict["fermi_energy"]
        efermi_units = scf_out_dict["fermi_energy_units"]
        if efermi_units != "eV":
            raise TypeError(
                "Error: Fermi energy is not in eV!"
                "it is {}".format(efermi_units)
            )
    except AttributeError:
        raise TypeError(
            "Error in retriving the SCF Fermi energy from pk: {}".format(
                scf_output_parameters.pk
            )
        )
    return efermi


def plot_bands(
    meta, path="", name="pw_bands", wannier_outputs=None, save_name="bands"
):
    from matplotlib.pyplot import plot, show, figure, savefig, xticks

    try:
        fermi_energy = get_fermi_energy(meta.scf_parameters)
    except TypeError as err:
        print(err)
        return False

    seekpath_parameters = meta.seekpath_parameters.get_dict()
    bands = meta.band_structure.get_bands()
    kxcoords = seekpath_parameters["explicit_kpoints_linearcoord"]

    fig = figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.grid(True, alpha=0.5)

    # set the limits
    ymin, ymax = fermi_energy - 10.0, fermi_energy + 10.0
    ymin = max(bands.min(), ymin) - 1
    ymax = min(bands.max(), ymax) + 1
    xmin, xmax = min(kxcoords), max(kxcoords)
    ax.set_ylim([ymin, ymax])
    ax.set_xlim([xmin, xmax])
    ax.set_title("Electronic bands structure - %s" % (name))
    ax.set_ylabel(r"Electronic bands ($eV$)")
    ax.hlines(
        fermi_energy,
        xmin,
        xmax,
        colors="r",
        linestyle="dashed",
        label="fermi energy",
    )
    labels = meta.band_structure.attributes["labels"]
    label_numbers = meta.band_structure.attributes["label_numbers"]
    for i in range(len(labels)):
        if labels[i] == "GAMMA":
            labels[i] = r"$\Gamma$"
        else:
            labels[i] = r"$%s$" % (labels[i])

    xbars = []
    for ilabel in range(len(labels)):
        xbar = kxcoords[label_numbers[ilabel]]
        ax.vlines(
            xbar,
            ymin,
            ymax,
            colors="black",
            linestyle="solid",
            linewidths=(0.1,),
            alpha=0.5,
        )
        xbars.append(xbar)
    for i in range(bands.shape[1]):
        ax.plot(kxcoords, bands[:, i])
        if wannier_outputs is not None:
            wannier_seekpath_parameters = (
                wannier_outputs.seekpath_parameters.get_dict()
            )
            wannier_kxcoords = wannier_seekpath_parameters[
                "explicit_kpoints_linearcoord"
            ]
            wannier_bands = (
                wannier_outputs.wannier90_interpolated_bands.get_bands()
            )
            ax.plot(wannier_kxcoords, wannier_bands[:, i])

    ax.set_xticks(xbars)
    ax.set_xticklabels(labels)
    if path != "":
        savefig(path)
    else:
        savefig("./%s.png" % (name if wannier_outputs is None else save_name))


def parse_label(label):
    if label == "GAMMA":
        label = r"$\Gamma$"
    else:
        label = r"$%s$" % (label)
    return label


def plot_bands_json(wannier, pw_bands):
    import json
    from matplotlib.pyplot import figure, savefig

    try:
        fermi_energy = get_fermi_energy(pw_bands.outputs.scf_parameters)
        name = pw_bands.inputs.structure.get_formula()
    except TypeError as err:
        print(err)
        return False

    fig = figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.grid(True, alpha=0.5)

    with open("pw_bands.json") as f:
        pw_bands_data = json.loads(f.read())
    with open("wannier_bands.json") as f:
        wannier_bands_data = json.loads(f.read())
    p_paths = pw_bands_data["paths"]
    p_bands = pw_bands.outputs.band_structure.get_bands()
    w_paths = wannier_bands_data["paths"]
    w_bands = wannier.outputs.wannier90_interpolated_bands.get_bands()
    labels = []
    labels_x = []
    p_x = []
    p_y = []
    w_x = []
    w_y = []

    # set the limits
    ymin, ymax = fermi_energy - 15.0, fermi_energy + 15.0
    ymin = max(w_bands.min(), ymin) - 1
    ymax = min(w_bands.max(), ymax) + 1
    ax.set_ylim([ymin, ymax])

    block_index = 0
    for pos in p_paths:
        p_x.extend(pos["x"])
        if block_index == 0:
            p_y = pos["values"]
        else:
            band_no = 0
            for band in p_y:
                band.extend(pos["values"][band_no])
                band_no += 1
        block_index += 1
    block_index = 0
    for pos in w_paths:
        if block_index > 0 and w_paths[block_index - 1]["length"] == 1:
            pass
        else:
            if pos["length"] == 1:
                label = parse_label(pos["from"]) + "|" + parse_label(pos["to"])
            else:
                label = parse_label(pos["from"])
            label_x = pos["x"][0]
            labels.append(label)
            labels_x.append(label_x)
            ax.vlines(
                label_x,
                ymin,
                ymax,
                colors="black",
                linestyle="solid",
                linewidths=(0.1,),
                alpha=0.5,
            )
        w_x.extend(pos["x"])
        if block_index == 0:
            w_y = pos["values"]
        else:
            band_no = 0
            for band in w_y:
                band.extend(pos["values"][band_no])
                band_no += 1
        block_index += 1

    labels.append(parse_label(w_paths[-1]["to"]))
    labels_x.append(w_paths[block_index - 1]["x"][-1])

    xmin, xmax = min(labels_x), max(labels_x)
    ax.set_title("Electronic bands structure - %s" % (name))
    ax.set_ylabel(r"Electronic bands ($eV$)")
    ax.hlines(
        fermi_energy,
        xmin,
        xmax,
        colors="r",
        linestyle="dashed",
        label="fermi energy",
    )

    for i in range(len(p_y)):
        ax.plot(p_x, p_y[i], color="k", linestyle=":", linewidth=0.8)
    for i in range(len(w_y)):
        ax.plot(w_x, w_y[i], linewidth=0.5)

    ax.set_xticks(labels_x)
    ax.set_xticklabels(labels)
    savefig("%s.eps" % (name), dpi=600, format="eps")
    savefig("%s.png" % (name), dpi=600)


def export_bands(wannier, pw_bands, plot_bands):
    wannier = load_node(wannier)
    pw_bands = load_node(pw_bands)
    wannier.outputs.wannier90_interpolated_bands.export(
        "wannier_bands.agr", overwrite=True
    )
    wannier.outputs.wannier90_interpolated_bands.export(
        "wannier_bands.gnu", "gnuplot", overwrite=True
    )
    wannier.outputs.wannier90_interpolated_bands.export(
        "wannier_bands.json", overwrite=True
    )
    wannier.outputs.wannier90_interpolated_bands.export(
        "wannier_bands.png", "mpl_png", overwrite=True
    )
    pw_bands.outputs.band_structure.export("pw_bands.agr", overwrite=True)
    pw_bands.outputs.band_structure.export(
        "pw_bands.gnu", "gnuplot", overwrite=True
    )
    pw_bands.outputs.band_structure.export("pw_bands.json", overwrite=True)
    pw_bands.outputs.band_structure.export(
        "pw_bands.png", "mpl_png", overwrite=True
    )

    if plot_bands:
        plot_bands_json(wannier, pw_bands)


def parse_arugments():
    parser = argparse.ArgumentParser(
        description="A script to plot bands of wannier workflow and pw_bands workflow."
    )
    parser.add_argument(
        "-W",
        "--wannier",
        help="aiida pk of Wannier Workflow",
    )
    parser.add_argument(
        "-B", "--pw_bands", help="aiida pk of PW Bands Workflow"
    )
    parser.add_argument(
        "-P",
        "--plot",
        default=False,
        action="store_true",
        help="Whether to plot bands.",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arugments()
    export_bands(args.wannier, args.pw_bands, args.plot)
