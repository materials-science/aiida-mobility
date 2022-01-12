import sys
import json
import importlib
from ase.atoms import default
import click
from aiida_mobility.cli.utils.options import PARAMETERS_SET
from aiida_mobility.utils import get_protocol
from . import cmd_root
from aiida_mobility.cli.utils import options


@cmd_root.group("protocols")
def cmd_protocols():
    """Commands to show protocols."""


@cmd_protocols.command("list")
@click.option(
    "-t",
    "--protocol_type",
    help="protocol for pw or others.",
    default="pw",
    type=click.Choice(["pw", "ph"], case_sensitive=False),
    show_choices=True,
)
@options.PROTOCOL(default=None)
def list_protocols(protocol_type, protocol):
    ipt = importlib.import_module(
        "aiida_mobility.utils.protocols.{}".format(protocol_type)
    )
    protocols = ipt._get_all_protocol_modifiers()

    if protocol is None:
        sys.stdout.write("* " + "\n* ".join(list(protocols.keys())))
    else:
        sys.stdout.write(
            "* " + "\n* ".join(list(protocols[protocol]["parameters"].keys()))
        )


@cmd_protocols.command("show")
@click.option(
    "-t",
    "--protocol_type",
    help="protocol for pw or others.",
    default="pw",
    type=click.Choice(["pw", "ph"], case_sensitive=False),
    show_choices=True,
)
@options.PROTOCOL()
@options.PARAMETERS_SET()
@options.STRUCTURE(default=None)
def show_protocol(protocol_type, protocol, parameters_set, structure):
    s = "* Protocol {} parameters {} detail :\n".format(
        protocol, parameters_set
    )

    if protocol_type == "pw":

        protocol, recommended_cutoffs = get_protocol(
            structure=structure,
            scf_parameters_name=parameters_set,
            protocol=protocol,
            pseudos=None,
        )
        ecutwfc = []
        ecutrho = []
        if structure is not None:
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
        protocol.pop("pseudo_data")
        s += json.dumps(protocol, sort_keys=True, indent=2)

        if len(ecutwfc) > 0 and len(ecutrho) > 0:
            s += "\n\n* Recommend cutoff for structure {} :\n".format(
                structure.get_formula()
            )
            s += "ecutwfc:  {}\n".format(max(ecutwfc))
            s += "ecutrho:  {}\n".format(max(ecutrho))

    elif protocol_type == "ph":
        from aiida_mobility.utils.protocols.ph import (
            get_ph_protocol_parameters,
        )

        protocol = get_ph_protocol_parameters(protocol, parameters_set)
        s += json.dumps(protocol, sort_keys=True, indent=2)

    sys.stdout.write(s)