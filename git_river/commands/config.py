# This file is part of git-river.
#
# Copyright Datto, Inc.
# Author: Sam Clements <sclements@datto.com>
#
# Licensed under the Mozilla Public License Version 2.0.
# Fedora-License-Identifier: MPLv2.0
# SPDX-2.0-License-Identifier: MPL-2.0
# SPDX-3.0-License-Identifier: MPL-2.0
#
# git-river is open source software.
# For more information on the license, see LICENSE.
# For more information on open source software, see https://opensource.org/osd.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import pathlib

import click

import git_river
import git_river.commands
import git_river.commands.clone
import git_river.commands.forge
import git_river.commands.repo
import git_river.config


@click.group(name="config")
def main():
    """Manage git-river's own configuration file."""
    pass


@main.command(name="display")
@click.pass_obj
def display_config(config: git_river.config.Config) -> None:
    """Dump the current configuration as JSON."""
    print(config.json(indent=2, by_alias=True))


@main.command(name="init")
@click.argument(
    "workspace",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        path_type=pathlib.Path,
    ),
)
@click.pass_obj
def init_config(config: git_river.config.Config, workspace: str) -> None:
    """Create the configuration file."""

    config.workspace = pathlib.Path(workspace)

    if git_river.config.CONFIG_PATH.exists():
        raise click.UsageError(f"Config file {git_river.config.CONFIG_PATH} already exists")

    if not git_river.config.CONFIG_DIRECTORY.exists():
        git_river.config.CONFIG_DIRECTORY.mkdir()

    git_river.config.CONFIG_PATH.write_text(config.json(indent=2, by_alias=True))


@main.command(name="workspace")
@click.pass_obj
def display_workspace(config: git_river.config.Config) -> None:
    """Print the workspace path."""
    print(config.workspace)
