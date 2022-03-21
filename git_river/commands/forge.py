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

import dataclasses
import itertools
import typing

import click
import structlog

import git_river.config
import git_river.ext.click
import git_river.repository

logger = structlog.get_logger(logger_name=__name__)


@dataclasses.dataclass()
class RepositoryManager:
    """Cache remote repos across multiple subcommands."""

    repos: typing.List[git_river.repository.RemoteRepository] = dataclasses.field(
        default_factory=list
    )

    def extend(self, repos: typing.Iterable[git_river.repository.RemoteRepository]) -> None:
        self.repos.extend(repos)

    def filter(self, f: typing.Callable[[git_river.repository.RemoteRepository], bool]) -> None:
        self.repos = [repo for repo in self.repos if f(repo)]

    def missing(self) -> typing.Sequence[git_river.repository.RemoteRepository]:
        return [repo for repo in self.repos if not repo.path.exists() and not repo.archived]

    def existing(self) -> typing.Sequence[git_river.repository.LocalRepository]:
        return [repo.as_local_repo() for repo in self.repos if repo.path.exists()]

    def empty(self) -> bool:
        return len(self.repos) == 0


@click.group(name="forge", invoke_without_command=True)
@click.option(
    "-f",
    "--forge",
    "forge",
    default=None,
    help="Use repositories from a specific forge.",
)
@click.pass_context
def main(
    ctx: click.Context,
    forge: typing.Optional[str],
) -> None:
    """
    Clone and manage repositories from GitLab and GitHub in bulk.

    Invokes the clone, configure, and remotes subcommands when no subcommand is given.
    """
    config = ctx.ensure_object(git_river.config.Config)
    manager = ctx.obj = RepositoryManager()

    if forge is not None:
        manager.extend(config.repositories_from_forge(forge))
    else:
        manager.extend(config.repositories())

    if manager.empty():
        ctx.fail("No repositories selected")

    if ctx.invoked_subcommand is None:
        ctx.invoke(clone_repositories)
        ctx.invoke(archived_repositories)
        ctx.invoke(configure_options)
        ctx.invoke(configure_remotes)


@main.command(name="archived")
@click.pass_obj
def archived_repositories(workspace: RepositoryManager) -> None:
    for repo in workspace.existing():
        if repo.archived:
            logger.warning("Local repository is archived", repo=repo.name)


@main.command(name="clone")
@click.pass_obj
def clone_repositories(workspace: RepositoryManager) -> None:
    """Clone all repositories from the configured users and groups."""
    repositories = workspace.missing()
    if not repositories:
        logger.debug("No repositories to clone")
        return

    logger.info("Cloning missing repositories", repositories=len(repositories))
    groups = itertools.groupby(repositories, key=lambda r: r.group)
    cloned = []
    for instance, iterable in groups:
        with git_river.ext.click.progressbar(
            iterable=list(iterable),
            event="Cloning missing repositories",
            item_show_func=lambda p: p.path.as_posix(),
            logger_name=__name__,
            instance=str(instance),
        ) as progress:
            for repo in progress:
                repo.clone(verbose=False)
                cloned.append(repo)

    for local_repo in cloned:
        local_repo.bind(logger).info("Cloned repository")


@main.command(name="configure")
@click.pass_obj
def configure_options(workspace: RepositoryManager) -> None:
    """Configure repository settings using the config file."""
    repositories = workspace.existing()
    logger.info("Configuring repository options", repositories=len(repositories))
    for repo in repositories:
        repo.configure_options()


@main.command(name="remotes")
@click.pass_obj
def configure_remotes(workspace: RepositoryManager) -> None:
    """Configure remotes from API metadata."""
    repositories = workspace.existing()
    logger.info("Configuring repository remotes", repositories=len(repositories))
    for repo in repositories:
        repo.configure_remotes()


@main.command(name="fetch")
@click.pass_obj
def fetch_remotes(workspace: RepositoryManager) -> None:
    """Fetch configured remotes for each repository."""
    with git_river.ext.click.progressbar(
        iterable=workspace.existing(),
        event="Fetching repository remotes",
        item_show_func=str,
        logger_name=__name__,
    ) as progress:
        for repo in progress:
            repo.fetch_remotes()


@main.command(name="tidy")
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    type=click.BOOL,
    default=False,
)
@click.option(
    "-t",
    "--target",
    "target",
    type=click.STRING,
    default=None,
    multiple=True,
    help="Check commits are merged into this branch.",
)
@click.pass_obj
def tidy(workspace: RepositoryManager, dry_run: bool, target: typing.Optional[str]) -> None:
    """
    Remove branches that have been merged into a target branch.

    If --branch is not set, uses the repositories configured default branch (for repositories
    discovered from a remote API), or the first branch found from 'main' and 'master'.
    """
    logger.info("Removing merged branches")
    for repo in workspace.existing():
        repo.remove_merged_branches(target=repo.target_or_mainline_branch(target), dry_run=dry_run)


@main.command(name="list")
@click.pass_obj
def list_repositories(workspace: RepositoryManager) -> None:
    """List all repositories from the configured users and groups."""
    for repo in workspace.existing():
        repo.bind(logger).info("Repository exists", remotes=repo.remote_names)
