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

from __future__ import annotations

import pathlib
import typing

import click
import structlog

import git_river.config
import git_river.ext.click
import git_river.repository

logger = structlog.get_logger(logger_name=__name__)


click_repo_option = click.option(
    "--repo",
    "path",
    default=pathlib.Path.cwd(),
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        path_type=pathlib.Path,
    ),
    envvar="GIT_RIVER_REPO",
    show_envvar=True,
    help="Path to the local repository, defaults to $CWD.",
)

click_target_option = click.option(
    "-t",
    "--target",
    "target",
    type=click.STRING,
    default=None,
    help="Branch commits are merged into. Defaults to the first of 'main' or 'master'.",
)

click_upstream_remote_option = click.option(
    "-u",
    "--upstream",
    "--upstream-remote",
    "upstream",
    type=click.STRING,
    default=None,
    help="Remote to consider the \"upstream\" remote. Defaults to 'upstream' or 'origin'.",
)

click_downstream_remote_option = click.option(
    "-d",
    "--downstream",
    "--downstream-remote",
    "downstream",
    type=click.STRING,
    default=None,
    help=(
        'Remote to consider the "downstream" remote. '
        "Defaults to the first of 'downstream' or 'origin'."
    ),
)

click_mainline_option = click.option(
    "-m",
    "--mainline",
    "--mainline-branch",
    "mainline",
    type=click.STRING,
    default=None,
    help="Branch to consider the \"mainline\" branch. Defaults to the first of 'main' or 'master'.",
)


@click.command(name="update")
@click_repo_option
def update_remotes(path: pathlib.Path) -> None:
    """Update and prune all remotes."""
    git_river.repository.LocalRepository.from_path(path).update_remotes()


@click.command(name="merge")
@click_repo_option
@click_mainline_option
@click.option(
    "-m",
    "--merge",
    "merge",
    type=click.STRING,
    default="merged",
    help="Branch that will contain the merged result.",
)
def merge_feature_branches(path: pathlib.Path, mainline: typing.Optional[str], merge: str) -> None:
    """
    Merge feature branches into a new 'merged' branch.

    By default, merges all branches prefixed 'feature/' into a branch named 'merged'.
    """
    repo = git_river.repository.LocalRepository.from_path(path)

    mainline = repo.discover_mainline_branch(mainline)

    repo.merge_feature_branches(target=mainline, merge=merge)


@click.command(name="tidy")
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    type=click.BOOL,
    default=False,
)
@click_mainline_option
@click_repo_option
def tidy_branches(path: pathlib.Path, dry_run: bool, mainline: typing.Optional[str]) -> None:
    """
    Remove branches that have been merged into a mainline branch.

    If --branch is not set, uses the repositories configured default branch (for repositories
    discovered from a remote API), or the first branch found from 'main' and 'master'.
    """
    repo = git_river.repository.LocalRepository.from_path(path)

    mainline = repo.discover_mainline_branch(mainline)

    repo.update_remotes()
    repo.remove_merged_branches(mainline, dry_run=dry_run)


@click.command(name="rebase")
@click_repo_option
@click_upstream_remote_option
@click_mainline_option
def rebase(
    path: pathlib.Path,
    upstream: typing.Optional[str],
    mainline: typing.Optional[str],
) -> None:
    """
    Rebase the currently checked out branch using the upstream mainline branch.
    """
    repo = git_river.repository.LocalRepository.from_path(path)

    upstream = repo.discover_upstream_remote(upstream)
    mainline = repo.discover_mainline_branch(mainline)

    repo.fetch_branch_from_remote(mainline, remote=upstream)
    repo.rebase(f"{upstream}/{mainline}")
    repo.remove_merged_branches(target=mainline, dry_run=False)


@click.command(name="end")
@click_repo_option
@click_upstream_remote_option
@click_downstream_remote_option
def end(
    path: pathlib.Path,
    upstream: typing.Optional[str],
    downstream: typing.Optional[str],
) -> None:
    """
    Prepare to start a new feature branch by returning to upstream/master and cleaning up.

    This is mostly useful when you're on a feature branch that has been merged into an upstream
    branch via a GitLab merge request or GitHub pull request.

    - Updates the mainline branch from the upstream remote.
    - Switches to the mainline branch.
    - Removes any branches that have been merged into the default branch.
    - Fetch all remotes and prunes local references to remote branches.
    - Pushes the mainline branch to the downstream remote (if a downstream remote exists).
    """
    repo = git_river.repository.LocalRepository.from_path(path)
    upstream = repo.discover_upstream_remote(upstream)
    mainline = repo.discover_mainline_branch()

    repo.fetch_branch_from_remote(mainline, remote=upstream)
    repo.switch_to_branch(mainline)
    repo.remove_merged_branches(mainline, dry_run=False)
    repo.update_remotes()

    if downstream := repo.discover_optional_downstream_remote(downstream):
        repo.push_to_remote(mainline, remote=downstream)
