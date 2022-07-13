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

import configparser
import dataclasses
import os
import pathlib
import typing

import click
import git
import giturlparse
import inflect
import structlog

p = inflect.engine()

logger = structlog.get_logger(logger_name=__name__)


class Missing(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class GitConfigKey:
    section: str
    option: str

    def __repr__(self) -> str:
        return f"{self.section}.{self.option}"

    def __str__(self) -> str:
        return f"{self.section}.{self.option}"

    @classmethod
    def parse(cls, key: str) -> GitConfigKey:
        section, option = key.split(".", maxsplit=1)
        return cls(section, option)


GitConfig = typing.Dict[GitConfigKey, typing.Optional[str]]


@dataclasses.dataclass()
class Repository:
    name: str
    path: pathlib.Path

    config: typing.Mapping[GitConfigKey, typing.Optional[str]] = dataclasses.field()
    remotes: typing.Mapping[str, typing.Optional[str]] = dataclasses.field()

    archived: bool = dataclasses.field()

    def __str__(self) -> str:
        return self.name

    def bind(self, log: structlog.stdlib.BoundLogger) -> structlog.stdlib.BoundLogger:
        return log.bind(name=self.name)

    @property
    def remote_names(self) -> typing.Sequence[str]:
        return list(self.remotes.keys())


@dataclasses.dataclass()
class RemoteRepository(Repository):
    clone_url: str = dataclasses.field()
    group: typing.Optional[str] = dataclasses.field(default=None)
    repo: typing.Optional[git.Repo] = dataclasses.field(default=None)
    default_branch: typing.Optional[str] = dataclasses.field(default=None)

    @classmethod
    def from_url(cls, workspace: pathlib.Path, url: str) -> RemoteRepository:
        parsed = giturlparse.parse(url)
        project, _ = os.path.splitext(parsed.pathname.removeprefix("/"))
        path = workspace.joinpath(parsed.domain, project)

        logger.debug(
            "Parsed repository from URL",
            url=url,
            path=path.as_posix(),
            domain=parsed.domain,
            project=project,
        )

        if pathlib.Path(project).is_absolute():
            raise Exception(f"Failed to parse repository url safely ({project=})")

        return cls(
            name=path.name,
            path=path,
            clone_url=url,
            config={},
            remotes={},
            group=parsed.domain,
            default_branch=None,
            archived=False,
        )

    def clone(self, verbose: bool = False) -> None:
        if self.path.exists():
            raise Exception(f"Repo {self.name} already exists ({self!r})")

        if self.clone_url is None:
            raise Exception(f"Repo {self.name} has no clone_url ({self!r})")

        if verbose:
            logger.info(
                "Cloning repository",
                name=self.name,
                url=self.clone_url,
                path=self.path.as_posix(),
            )

        self.repo = git.Repo.clone_from(url=self.clone_url, to_path=self.path)

    def ensure_repo(self) -> git.Repo:
        if self.repo is None:
            return git.Repo(self.path.as_posix())

        return self.repo

    def as_local_repo(self) -> LocalRepository:
        repo = self.ensure_repo()
        return LocalRepository(
            name=self.name,
            path=self.path,
            config=self.config,
            remotes=self.remotes,
            archived=self.archived,
            repo=repo,
            default_branch=self.default_branch,
        )


@dataclasses.dataclass()
class LocalRepository(Repository):
    repo: git.Repo = dataclasses.field(repr=False)
    default_branch: typing.Optional[str] = dataclasses.field(default=None)

    @classmethod
    def from_path(cls, path: pathlib.Path) -> LocalRepository:
        return cls(
            name=path.name,
            path=path,
            config={},
            remotes={},
            archived=False,
            repo=git.Repo(path.as_posix()),
        )

    def configure_options(self):
        """Configure generic settings from the '.config' map."""
        log = self.bind(logger)
        log.debug("Configuring repository options")

        with self.repo.config_writer() as writer:
            for key, value in self.config.items():
                try:
                    current = writer.get_value(key.section, key.option)
                except (configparser.NoSectionError, configparser.NoOptionError):
                    current = None

                if current == value:
                    log.debug("Git config is correct", key=str(key), value=current)
                    continue

                if value is None:
                    log.info("Removing git config", key=str(key))
                    writer.remove_option(section=key.section, option=key.option)
                    continue

                log.info("Writing git config", key=str(key), value=value)
                writer.set_value(section=key.section, option=key.option, value=value)

    def configure_remotes(self) -> None:
        """Configure remote names and URLs."""
        self.bind(logger).debug("Configuring repository remotes")

        for name, url in self.remotes.items():
            if url is None:
                self.delete_remote(name)
            else:
                self.create_remote(name, url)

    def delete_remote(self, name) -> None:
        try:
            remote = self.repo.remote(name)
        except ValueError:
            pass
        else:
            self.bind(logger).info("Deleting remote", remote=name)
            self.repo.delete_remote(remote)

    def create_remote(self, name: str, url: str) -> None:
        log = self.bind(logger)

        try:
            remote = self.repo.remote(name)
        except ValueError:
            log.info("Creating remote", remote=name, url=url)
            remote = self.repo.create_remote(name, url)

        if set(remote.urls) != {url}:
            log.warning("Updating remote", remote=name, new={url}, old=set(remote.urls))
            remote.set_url(url)

    def update_remotes(self, prune: bool = True) -> None:
        """Update (and prune) all remotes using 'git remote update'."""
        log = self.bind(logger)
        log.info("Updating remotes")
        self.repo.git._call_process("remote", "update", insert_kwargs_after="update", prune=prune)

    def remove_merged_branches(self, target: str, *, dry_run: bool = True) -> None:
        """Remove branches that have been merged into the repo's default branch."""
        log = self.bind(logger).bind(target=target, dry_run=dry_run)
        merged_branches = self.merged(target)
        active_branch = self.repo.active_branch.name
        for merged_branch in merged_branches:
            if active_branch == merged_branch:
                log.debug("Skipping current branch", head=merged_branch)
                continue

            if merged_branch.startswith("release/"):
                log.debug("Skipping release/* branch", head=merged_branch)
                continue

            if dry_run:
                log.info("Would delete branch", head=merged_branch)
            else:
                log.info("Deleting branch", head=merged_branch)
                self.repo.delete_head(merged_branch)

    def merged(self, target: str) -> typing.Set[str]:
        """Return a list of branches merged into a target branch."""
        log = self.bind(logger)
        rc, stdout, stderr = self.repo.git.branch(
            "--list",
            "--format=%(refname:short)",
            "--merged",
            target,
            with_extended_output=True,
        )
        log.debug("Ran git branch", target=target, rc=rc, stdout=stdout, stderr=stderr)
        merged = {line.lstrip() for line in stdout.splitlines()} - {target}
        log.debug("Found merged branches", target=target, merged=merged)
        return merged

    def merge_feature_branches(self, *, prefix: str = "feature/", target: str, merge: str) -> None:
        log = self.bind(logger).bind(prefix=prefix, target=target, merge=merge)

        target_branch = self.repo.heads[target]

        feature_branches = {head for head in self.repo.heads if head.name.startswith(prefix)}
        if not feature_branches:
            raise click.UsageError("No feature branches found")
        for feature_branch in feature_branches:
            log.info(f"Selected feature branch", branch=feature_branch)
        base = self.repo.merge_base(*feature_branches)
        log.info("Found merge base", base=base)

        if merge in self.repo.heads:
            log.info("Using existing merge branch")
            merge_branch = self.repo.heads[merge]
        else:
            log.info("Creating merge branch")
            merge_branch = self.repo.create_head(merge, target)

        log.info("Checking out merge branch")
        merge_branch.checkout()

        log.info("Resetting to target branch")
        self.repo.head.reference = self.repo.heads[target]
        self.repo.head.reset(index=True, working_tree=False)

        log.info("Merging into index")
        self.repo.index.merge_tree(rhs=merge_branch, base=base)

        log.info("Committing to merge branch")
        message = "WIP: Merge branches {branches} into '{target}'".format(
            branches=p.join([f"'{branch}'" for branch in feature_branches]),
            target=target_branch,
        )
        parent_commits = [branch.commit for branch in feature_branches]
        self.repo.index.commit(message=message, parent_commits=parent_commits)  # type: ignore

    def fetch_branch_from_remote(self, branch: str, *, remote: str) -> None:
        """
        --update-head-ok is set as we don't mind fetching into the current branch.
        """
        self.bind(logger).info("Fetching branch", branch=branch, remote=remote)
        self.repo.git.fetch(remote, f"{branch}:{branch}", "--update-head-ok")

    def switch_to_branch(self, branch: str) -> None:
        self.bind(logger).info("Switching to branch", branch=branch)
        self.repo.git.switch(branch, "--no-guess")

    def push_to_remote(self, branch: str, *, remote: str) -> None:
        self.bind(logger).info("Pushing to remote", branch=branch, remote=remote)
        self.repo.git.push(remote, f"{branch}:{branch}")

    def rebase(self, branch: str) -> None:
        self.bind(logger).info("Rebasing", branch=branch)
        self.repo.git.rebase(branch)

    def discover_branch(self, *names: str) -> str:
        for name in names:
            try:
                return self._head(name)
            except IndexError:
                pass

        raise Missing(f"No heads found for {names!r}")

    def discover_mainline_branch(self, override: typing.Optional[str] = None) -> str:
        if override is not None:
            return self._head(override)

        if self.default_branch is not None:
            return self.default_branch

        return self.discover_branch("main", "master")

    def discover_remote(self, *names: str) -> str:
        for name in names:
            try:
                return self._remote(name)
            except ValueError:
                pass

        raise Missing(f"No remotes found for {names!r}")

    def discover_upstream_remote(self, override: typing.Optional[str] = None) -> str:
        if override is not None:
            return self._remote(override)

        return self.discover_remote("upstream", "origin")

    def discover_downstream_remote(self, override: typing.Optional[str] = None) -> str:
        if override is not None:
            return self._remote(override)

        return self.discover_remote("downstream")

    def discover_optional_downstream_remote(
        self,
        override: typing.Optional[str] = None,
    ) -> typing.Optional[str]:
        """
        If we can't find a downstream remote, return None instead of raising an error.

        An error is still raised if a remote was explicitly specified.
        """
        if override is not None:
            return self._remote(override)

        try:
            return self.discover_remote("downstream")
        except Missing:
            return None

    def _head(self, name: str) -> str:
        """Check a head exists."""
        try:
            head = self.repo.heads[name]
        except ValueError as error:
            raise Missing(f"No head found named {name!r}") from error
        return head.name

    def _remote(self, name: str) -> str:
        """Check a remote exists."""
        try:
            remote = self.repo.remote(name)
        except ValueError as error:
            raise Missing(f"No remote found named {name!r}") from error
        return remote.name
