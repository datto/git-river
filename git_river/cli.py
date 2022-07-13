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

import click
import pydantic.error_wrappers

import git_river
import git_river.commands
import git_river.commands.clone
import git_river.commands.forge
import git_river.commands.config
import git_river.commands.repo
import git_river.config


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    git_river.config.configure_logging()
    try:
        ctx.obj = git_river.config.Config()
    except pydantic.error_wrappers.ValidationError as error:
        raise click.UsageError(str(error)) from error


main.add_command(git_river.commands.clone.main)
main.add_command(git_river.commands.config.main)
main.add_command(git_river.commands.forge.main)
main.add_command(git_river.commands.repo.update_remotes)
main.add_command(git_river.commands.repo.merge_feature_branches)
main.add_command(git_river.commands.repo.tidy_branches)
main.add_command(git_river.commands.repo.rebase)
main.add_command(git_river.commands.repo.end)
