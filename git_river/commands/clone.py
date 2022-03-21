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

import typing

import click
import structlog

import git_river.config
import git_river.ext.click

logger = structlog.get_logger(logger_name=__name__)


@click.command(name="clone")
@click.argument(
    "repositories",
    metavar="REPOSITORY",
    type=click.STRING,
    nargs=-1,
)
@click.pass_obj
def main(config: git_river.config.Config, repositories: typing.Sequence[str]) -> None:
    """Clone a repository to the workspace path."""
    for url in repositories:
        config.repository_from_url(url).clone(verbose=True)
