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

import abc
import json
import logging
import logging.handlers
import pathlib
import typing

import appdirs
import github
import github.MainClass
import github.Repository
import gitlab
import gitlab.v4.objects
import pydantic
import structlog
import structlog.stdlib

import git_river
import git_river.ext.click
import git_river.ext.gitlab
from git_river.repository import GitConfigKey, RemoteRepository

logger = structlog.get_logger(logger_name=__name__)

CONFIG_DIRECTORY = pathlib.Path(appdirs.user_config_dir(git_river.__app__))
CACHE_DIRECTORY = pathlib.Path(appdirs.user_cache_dir(git_river.__app__))
CONFIG_PATH = CONFIG_DIRECTORY / "config.json"


class Forge(pydantic.BaseModel, abc.ABC):
    gitconfig: typing.Mapping[str, typing.Optional[str]] = pydantic.Field(default_factory=dict)
    exclude: typing.Set[str] = pydantic.Field(default_factory=set)

    class Config:
        # Validate default values - essential so that base_url is converted to pydantic.HttpUrl.
        validate_all = True

    def __str__(self) -> str:
        return self.domain

    @property
    @abc.abstractmethod
    def domain(self) -> str:
        raise NotImplementedError

    def git_config_options(self) -> typing.MutableMapping[GitConfigKey, typing.Optional[str]]:
        return {GitConfigKey.parse(key): value for key, value in self.gitconfig.items()}

    def excluded_by_name(self, name: str) -> bool:
        return name in self.exclude

    @abc.abstractmethod
    def remote_repositories(self, workspace: pathlib.Path) -> typing.Iterable[RemoteRepository]:
        raise NotImplementedError


class GitLab(Forge):
    type: typing.Literal["gitlab"]

    base_url: pydantic.HttpUrl = pydantic.Field(default="https://gitlab.com")
    private_token: pydantic.SecretStr = pydantic.Field()

    users: typing.Sequence[str] = pydantic.Field(default_factory=list)
    groups: typing.Sequence[str] = pydantic.Field(default_factory=list)
    self: bool = pydantic.Field(default=True)

    @property
    def domain(self) -> str:
        if self.base_url.host is None:
            raise Exception(f"Could not determine host for {self.base_url!r}")

        return self.base_url.host

    def all_projects(self) -> typing.Iterable[git_river.ext.gitlab.Project]:
        client = gitlab.Gitlab(
            url=self.base_url,
            private_token=self.private_token.get_secret_value(),
        )
        log = logger.bind(type="GitLab", url=client.url)

        for path in self.groups:
            log.info("Listing GitLab group projects", id=path)
            group = client.groups.get(path, lazy=True)
            yield from group.projects.list(  # type: ignore
                all=True,
                per_page=100,
                archived=False,
                as_list=False,
                include_subgroups=True,
            )

        for path in self.users:
            log.info("Listing GitLab user projects", id=path)
            user = client.users.get(path, lazy=True)
            yield from user.projects.list(  # type: ignore
                all=True,
                per_page=100,
                archived=False,
                as_list=False,
                include_subgroups=True,
            )

        if self.self:
            log.debug("Getting current GitLab user")
            client.auth()

            if client.user:
                log.info("Listing GitLab self projects", id=client.user.id)
                user = client.users.get(client.user.id, lazy=True)
                yield from user.projects.list(  # type: ignore
                    all=True,
                    archived=False,
                    as_list=False,
                    include_subgroups=True,
                    per_page=100,
                )

    def projects(self) -> typing.Iterable[git_river.ext.gitlab.Project]:
        for project in self.all_projects():
            if self.excluded_by_name(project.path):
                logger.debug("Excluding project", project=project, path=project.path)
                continue

            yield project

    def remote_repositories(self, workspace: pathlib.Path) -> typing.Iterable[RemoteRepository]:
        forge_config = self.git_config_options()

        for project in self.projects():
            if parent := git_river.ext.gitlab.forked_from_project(project):
                remote_config = {GitConfigKey("remote", "pushdefault"): "downstream"}
                remotes = {
                    "origin": None,
                    "upstream": parent["ssh_url_to_repo"],
                    "downstream": project.ssh_url_to_repo,
                }
            else:
                remote_config = {GitConfigKey("remote", "pushdefault"): "origin"}
                remotes = {"origin": project.ssh_url_to_repo}

            yield RemoteRepository(
                clone_url=project.ssh_url_to_repo,
                config={**remote_config, **forge_config},
                group=str(self),
                name=f"{self.domain}/{project.path_with_namespace}",
                path=workspace / self.domain / project.path_with_namespace,
                remotes=remotes,
                default_branch=project.default_branch,
                archived=project.archived,
            )


class GitHub(Forge):
    type: typing.Literal["github"]

    base_url: pydantic.HttpUrl = pydantic.Field("https://api.github.com")
    login_or_token: pydantic.SecretStr = pydantic.Field()

    users: typing.Sequence[str] = pydantic.Field(default_factory=list)
    organizations: typing.Sequence[str] = pydantic.Field(default_factory=list)
    self: bool = pydantic.Field(default=True)

    @property
    def domain(self) -> str:
        if self.base_url.host is None:
            raise Exception(f"Could not determine host for {self.base_url!r}")

        if self.base_url.host.startswith("api."):
            return self.base_url.host.removeprefix("api.")

        return self.base_url.host

    def all_repositories(self) -> typing.Iterable[github.Repository.Repository]:
        client = github.Github(
            base_url=self.base_url,
            login_or_token=self.login_or_token.get_secret_value(),
        )
        log = logger.bind(type="GitHub", url=self.base_url)

        for organization in self.organizations:
            log.info("Listing GitHub organisation repos", id=organization)
            yield from client.get_organization(organization).get_repos()

        for user in self.users:
            log.info("Listing GitHub user repos", id=user)
            yield from client.get_user(user).get_repos()

        if self.self:
            auth = client.get_user()
            log.info("Listing GitHub self repos", id=auth.id)
            yield from client.get_user().get_repos()

    def repositories(self) -> typing.Iterable[github.Repository.Repository]:
        for repository in self.all_repositories():
            if self.excluded_by_name(repository.name):
                logger.debug("Excluding project", repository=repository, name=repository.name)
                continue

            yield repository

    def remote_repositories(self, workspace: pathlib.Path) -> typing.Iterable[RemoteRepository]:
        forge_config = self.git_config_options()

        for repository in self.repositories():
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

            yield RemoteRepository(
                clone_url=repository.ssh_url,
                config={**remote_config, **forge_config},
                group=str(self),
                name=f"{self.domain}/{repository.full_name}",
                path=workspace / self.domain / repository.full_name,
                remotes=remotes,
                default_branch=repository.default_branch,
                archived=repository.archived,
            )


class Config(pydantic.BaseSettings):
    workspace: pathlib.Path = pydantic.Field(env="GIT_RIVER_WORKSPACE", default=None)
    forges: typing.Mapping[str, typing.Union[GitHub, GitLab]] = pydantic.Field(default_factory=dict)

    class Config:
        env_prefix = "UPSTREAM_"
        env_file_encoding = "utf-8"

        extra = pydantic.Extra.ignore

        @classmethod
        def config_settings(cls, _: Config) -> typing.Dict[str, typing.Any]:
            if not CONFIG_PATH.exists():
                logger.debug("No config file exists", path=CONFIG_PATH.as_posix())
                return {}

            logger.debug("Parsing config file", path=CONFIG_PATH.as_posix())
            return json.loads(CONFIG_PATH.read_text())

        @classmethod
        def customise_sources(
            cls,
            init_settings: pydantic.env_settings.SettingsSourceCallable,
            env_settings: pydantic.env_settings.SettingsSourceCallable,
            file_secret_settings: pydantic.env_settings.SettingsSourceCallable,
        ):
            return (
                init_settings,
                env_settings,
                file_secret_settings,
                cls.config_settings,
            )

    @classmethod
    @pydantic.validator("workspace")
    def workspace_path_must_be_set(cls, value: typing.Optional[pathlib.Path]) -> pathlib.Path:
        if value is None:
            raise ValueError(
                "Workspace is not configured - set 'workspace' in {config_path} or set the "
                "'GIT_RIVER_WORKSPACE' environment variable".format(config_path=CONFIG_PATH)
            )

        return value

    def repository_from_url(self, url: str) -> RemoteRepository:
        return RemoteRepository.from_url(self.workspace, url)

    def repositories_from_forge(self, key: str) -> typing.Iterable[RemoteRepository]:
        return self.forges[key].remote_repositories(self.workspace)

    def repositories(self) -> typing.Iterable[RemoteRepository]:
        for key in self.forges.keys():
            yield from self.repositories_from_forge(key)


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(sort_keys=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
    )

    CACHE_DIRECTORY.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        filename=str(CACHE_DIRECTORY / "debug.log"),
        maxBytes=1024 * 1024,
    )
    handler.setFormatter(logging.Formatter("{asctime}:{levelname}:{name}:{message}", style="{"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
