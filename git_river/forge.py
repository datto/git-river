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

import abc
import dataclasses
import pathlib
import typing

import github
import gitlab
import structlog

from git_river.ext.gitlab import GitLabProject, forked_from_project
from git_river.repository import GitConfig, GitConfigKey, RemoteRepository


logger = structlog.get_logger(logger_name=__name__)


class Forge(abc.ABC):
    pass


@dataclasses.dataclass()
class GitHub(Forge):
    client: github.Github
    domain: str
    gitconfig: GitConfig
    workspace: pathlib.Path

    logger: structlog.BoundLogger = dataclasses.field(init=False)

    def __post_init__(self):
        self.logger = logger.bind(type="GitHub", domain=self.domain)

    def repositories_organization(self, organization: str) -> typing.Iterable[RemoteRepository]:
        self.logger.info("Listing GitHub organisation repos", id=organization)
        repos = self.client.get_organization(organization).get_repos()
        return [self._into_repository(repo) for repo in repos]

    def repositories_user(self, user: str) -> typing.Iterable[RemoteRepository]:
        self.logger.info("Listing GitHub user repos", id=user)
        repos = self.client.get_user(user).get_repos()
        return [self._into_repository(repo) for repo in repos]

    def repositories_self(self) -> typing.Iterable[RemoteRepository]:
        auth = self.client.get_user()
        self.logger.info("Listing GitHub self repos", id=auth.login)
        repos = self.client.get_user(auth.login).get_repos()
        return [self._into_repository(repo) for repo in repos]

    def _into_repository(self, repository) -> RemoteRepository:
        if repository.parent is None:
            remote_config = {GitConfigKey("remote", "pushdefault"): "origin"}
            remotes = {"origin": repository.ssh_url}
        else:
            remote_config = {GitConfigKey("remote", "pushdefault"): "downstream"}
            remotes = {
                "origin": None,
                "upstream": repository.parent.ssh_url,
                "downstream": repository.ssh_url,
            }

        return RemoteRepository(
            clone_url=repository.ssh_url,
            config={**remote_config, **self.gitconfig},
            group=self.domain,
            name=f"{self.domain}/{repository.full_name}",
            path=self.workspace / self.domain / repository.full_name,
            remotes=remotes,
            default_branch=repository.default_branch,
            archived=repository.archived,
        )


@dataclasses.dataclass()
class GitLab(Forge):
    client: gitlab.Gitlab
    domain: str
    gitconfig: GitConfig
    workspace: pathlib.Path

    logger: structlog.BoundLogger = dataclasses.field(init=False)

    def __post_init__(self):
        self.logger = logger.bind(type="GitLab", domain=self.domain)

    def repositories_group(self, identifier: str) -> typing.Iterable[RemoteRepository]:
        self.logger.info("Listing GitLab group projects", id=identifier)
        group = self.client.groups.get(identifier, lazy=True)
        return self._repositories(group)

    def repositories_user(self, identifier: str) -> typing.Iterable[RemoteRepository]:
        self.logger.info("Listing GitLab user projects", id=identifier)
        user = self.client.users.get(identifier, lazy=True)
        return self._repositories(user)

    def repositories_self(self) -> typing.Iterable[RemoteRepository]:
        self.logger.debug("Getting current GitLab user")
        self.client.auth()

        if not self.client.user:
            self.logger.debug("Not logged in")
            return []

        user = self.client.users.get(self.client.user.id)
        self.logger.info("Listing GitLab self projects", id=user.username)
        return self._repositories(user)

    def _repositories(self, obj) -> typing.Iterable[RemoteRepository]:
        projects = obj.projects.list(  # type: ignore
            all=True,
            per_page=100,
            archived=False,
            as_list=False,
            include_subgroups=True,
        )
        return [self._into_repository(project) for project in projects]

    def _into_repository(self, project) -> RemoteRepository:
        if parent := forked_from_project(project):
            remote_config = {GitConfigKey("remote", "pushdefault"): "downstream"}
            remotes = {
                "origin": None,
                "upstream": parent["ssh_url_to_repo"],
                "downstream": project.ssh_url_to_repo,
            }
        else:
            remote_config = {GitConfigKey("remote", "pushdefault"): "origin"}
            remotes = {"origin": project.ssh_url_to_repo}

        return RemoteRepository(
            clone_url=project.ssh_url_to_repo,
            config={**remote_config, **self.gitconfig},
            group=self.domain,
            name=project.path_with_namespace,
            path=self.workspace / self.domain / project.path_with_namespace,
            remotes=remotes,
            default_branch=project.default_branch,
            archived=project.archived,
        )
