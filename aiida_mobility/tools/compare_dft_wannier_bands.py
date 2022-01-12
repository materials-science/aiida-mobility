#!/usr/bin/env runaiida
"""compare DFT and Wannier band structures
"""
import argparse
from aiida import orm
import numpy as np


def distEclud(x, y):
    return np.sqrt(np.sum((x - y) ** 2))


# TODO: compare_bands_data
def compare_bands_data(
    dft_bands, wan_bands, emin=None, emax=None, fermi_energy=None
):
    if dft_bands.shape[0] == wan_bands.shape[0]:
        inner_dft_bands = range(0, dft_bands.shape[1])
        inner_wan_bands = range(0, wan_bands.shape[1])

        if all(e is not None for e in (emin, emax)):
            index = 0
            inner_dft_bands = []
            inner_wan_bands = []
            while index < dft_bands.shape[1] and index < wan_bands.shape[1]:
                dband = dft_bands[:, index]
                wband = wan_bands[:, index]
                if np.max(dband) > emin and np.min(dband) < emax:
                    inner_dft_bands.append(index)
                if np.max(wband) > emin and np.min(wband) < emax:
                    inner_wan_bands.append(index)
            while index < dft_bands.shape[1]:
                dband = dft_bands[:, index]
                if np.max(dband) > emin and np.min(dband) < emax:
                    inner_dft_bands.append(index)
            while index < wan_bands.shape[1]:
                wband = wan_bands[:, index]
                if np.max(wband) > emin and np.min(wband) < emax:
                    inner_wan_bands.append(index)

        diff_num = len(inner_dft_bands) - len(inner_wan_bands)
        if diff_num == 0:
            diff = distEclud(inner_wan_bands, inner_dft_bands)
        elif diff_num > 0:
            diff = [
                distEclud(
                    inner_wan_bands,
                    inner_dft_bands[:, disp : disp + len(inner_wan_bands)],
                )
                for disp in range(0, diff_num)
            ]
        elif diff_num < 0:
            diff = [
                distEclud(
                    inner_wan_bands[:, disp : disp + len(inner_dft_bands)],
                    inner_dft_bands,
                )
                for disp in range(0, abs(diff_num))
            ]
        # min_diff = np.min(diff, axis=0)
        return diff


def required_length(nmin, nmax):
    class RequiredLength(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not nmin <= len(values) <= nmax:
                msg = 'argument "{f}" requires between {nmin} and {nmax} arguments'.format(
                    f=self.dest, nmin=nmin, nmax=nmax
                )
                raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, values)

    return RequiredLength


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"Plot DFT and Wannier bands for comparison."
    )
    parser.add_argument(
        "pk",
        metavar="PK",
        type=int,
        nargs="+",
        action=required_length(1, 2),
        help="The PK of a Wannier90BandsWorkChain, the `compare_dft_bands` inputs of the Wannier90BandsWorkChain should be True; or PKs of 2 BandsData to be compared.",
    )
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="save as a python plotting script instead of showing matplotlib window",
    )
    args = parser.parse_args()

    input_is_workchain = len(args.pk) == 1
    if input_is_workchain:
        workchain = orm.load_node(args.pk[0])
        dft_bands = workchain.outputs.dft_bands
        wan_bands = workchain.outputs.wannier90_interpolated_bands
    else:
        dft_bands = orm.load_node(args.pk[0])
        wan_bands = orm.load_node(args.pk[1])

    # dft_bands.show_mpl()
    dft_mpl_code = dft_bands._exportcontent(
        fileformat="mpl_singlefile", legend=f"{dft_bands.pk}", main_file_name=""
    )[0]
    wan_mpl_code = wan_bands._exportcontent(
        fileformat="mpl_singlefile",
        legend=f"{wan_bands.pk}",
        main_file_name="",
        bands_color="r",
        bands_linestyle="dashed",
    )[0]

    dft_mpl_code = dft_mpl_code.replace(b"pl.show()", b"")
    wan_mpl_code = wan_mpl_code.replace(b"fig = pl.figure()", b"")
    wan_mpl_code = wan_mpl_code.replace(b"p = fig.add_subplot(1,1,1)", b"")
    mpl_code = dft_mpl_code + wan_mpl_code

    formula = workchain.inputs.structure.get_formula()
    # add title
    if input_is_workchain:
        replacement = f"workchain pk {workchain.pk}, {formula}, dft_bands pk {dft_bands.pk}, wan_bands pk {wan_bands.pk}"
    else:
        replacement = (
            f"1st bands pk {dft_bands.pk}, 2nd bands pk {wan_bands.pk}"
        )
    replacement = f'p.set_title("{replacement}")\npl.show()'
    mpl_code = mpl_code.replace(b"pl.show()", replacement.encode())

    if input_is_workchain:
        fname = f"bandsdiff_{formula}_{workchain.pk}.py"
    else:
        fname = f"bandsdiff_{dft_bands.pk}_{wan_bands.pk}.png"

    if args.save:
        with open(fname, "w") as f:
            f.write(mpl_code.decode())
    else:
        exec(mpl_code)