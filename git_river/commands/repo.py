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
    help="Branch commits are merged into. Defaults to main or master if they exist.",
)

click_upstream_remote_option = click.option(
    "-u",
    "--upstream",
    "--upstream-remote",
    "upstream",
    type=click.STRING,
    default=None,
    help="Branch to consider the upstream remote. Defaults to upstream.",
)

click_downstream_remote_option = click.option(
    "-d",
    "--downstream",
    "--downstream-remote",
    "downstream",
    type=click.STRING,
    default=None,
    help=(
        "Branch to consider the downstream remote. "
        "Defaults to the first of 'downstream' or 'origin'."
    ),
)


@click.command(name="configure")
@click_repo_option
def configure_options(path: pathlib.Path) -> None:
    """Configure options."""
    git_river.repository.LocalRepository.from_path(path).configure_options()


@click.command(name="remotes")
@click_repo_option
def configure_remotes(path: pathlib.Path) -> None:
    """Configure remotes."""
    git_river.repository.LocalRepository.from_path(path).configure_remotes()


@click.command(name="fetch")
@click_repo_option
def fetch_remotes(path: pathlib.Path) -> None:
    """Fetch all remotes."""
    git_river.repository.LocalRepository.from_path(path).fetch_remotes()


@click.command(name="merge")
@click_repo_option
@click_target_option
@click.option(
    "-m",
    "--merge",
    "merge",
    type=click.STRING,
    default="merged",
    help="Branch that will contain the merged result.",
)
def merge_feature_branches(path: pathlib.Path, target: typing.Optional[str], merge: str) -> None:
    """
    Merge feature branches into a new 'merged' branch.

    By default, merges all branches prefixed 'feature/' into a branch named 'merged'.
    """
    repo = git_river.repository.LocalRepository.from_path(path)
    repo.merge_feature_branches(target=repo.target_or_mainline_branch(target), merge=merge)


@click.command(name="tidy")
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    type=click.BOOL,
    default=False,
)
@click_target_option
@click_repo_option
def tidy_branches(path: pathlib.Path, dry_run: bool, target: typing.Optional[str]) -> None:
    """
    Remove branches that have been merged into a target branch.

    If --branch is not set, uses the repositories configured default branch (for repositories
    discovered from a remote API), or the first branch found from 'main' and 'master'.
    """
    repo = git_river.repository.LocalRepository.from_path(path)
    repo.fetch_remotes(prune=True)
    repo.remove_merged_branches(repo.target_or_mainline_branch(target), dry_run=dry_run)


@click.command(name="restart")
@click_repo_option
@click_upstream_remote_option
def restart(
    path: pathlib.Path,
    upstream: typing.Optional[str],
) -> None:
    """
    Rebase the currently checked out branch using the upstream mainline branch.
    """
    repo = git_river.repository.LocalRepository.from_path(path)
    upstream = repo.discover_remote(upstream, "upstream")
    mainline = repo.discover_mainline_branch()

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

    - Updates the default branch from the 'upstream' remote.
    - Switches to the default branch.
    - Removes any branches that have been merged into the default branch.
    - Prunes local references to remote branches.
    """
    repo = git_river.repository.LocalRepository.from_path(path)
    upstream = repo.discover_remote(upstream, "upstream")
    downstream = repo.discover_remote(downstream, "downstream", "origin")
    branch = repo.discover_mainline_branch()

    repo.fetch_branch_from_remote(branch, remote=upstream)
    repo.switch_to_branch(branch)
    repo.remove_merged_branches(branch, dry_run=False)
    repo.fetch_remotes(prune=True)
    repo.push_to_remote(branch, remote=downstream)
