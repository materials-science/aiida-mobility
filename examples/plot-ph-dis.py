"""
Author: your name
Date: 2021-11-08 09:58:44
LastEditTime: 2021-11-08 09:58:44
LastEditors: your name
Description: In User Settings Edit
FilePath: /aiida-mobility/examples/plot-ph-dis.py
"""
#!/usr/bin/env python
import sys
from matplotlib.pyplot import plot, show, figure, savefig, xticks

dat_filename = sys.argv[1]
labels = ["GAMMA", "X", "K", "GAMMA", "L"]
label_frac = 200
label_numbers = []


x_data = []
y_data = []
fig = figure()
ax = fig.add_subplot(1, 1, 1)
ax.grid(True, alpha=0.5)
ax.set_title("Phonon Dispersion")
ax.set_ylabel(r"Frequencies ($Hz$)")

with open(dat_filename, "r") as f:
    x_data = [float(row.split()[0]) for row in f.readlines()]

for i in range(len(labels)):
    if labels[i] == "GAMMA":
        labels[i] = r"$\Gamma$"
    else:
        labels[i] = r"$%s$" % (labels[i])

xbars = []
for ilabel in range(len(labels)):
    if len(label_numbers) != len(label_frac):
        pass
    else:
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