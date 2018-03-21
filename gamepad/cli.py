# -*- coding: utf-8 -*-

"""Console script for gamepad."""
import sys
import click

from gamepad.gamepad import Gamepad


@click.command()
def main(args=None):
    """Console script for gamepad."""

    controller = Gamepad()
    controller.watch_all()

    click.echo("Connect a gamepad and start mashing buttons!")

    input("Press ENTER to quit\n\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
