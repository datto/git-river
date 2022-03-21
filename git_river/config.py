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
import click
import github
import github.MainClass
import github.Repository
import gitlab
import gitlab.v4.objects
import pydantic
import structlog
import structlog.stdlib

import git_river
from git_river.repository import GitConfig, GitConfigKey, RemoteRepository
from git_river.forge import GitHub, GitLab

logger = structlog.get_logger(logger_name=__name__)

CONFIG_DIRECTORY = pathlib.Path(appdirs.user_config_dir(git_river.__app__))
CACHE_DIRECTORY = pathlib.Path(appdirs.user_cache_dir(git_river.__app__))
CONFIG_PATH = CONFIG_DIRECTORY / "config.json"


class ForgeConfig(pydantic.BaseModel, abc.ABC):
    gitconfig: typing.Mapping[str, typing.Optional[str]] = pydantic.Field(default_factory=dict)

    class Config:
        # Validate default values - essential so that base_url is converted to pydantic.HttpUrl.
        validate_all = True

    def git_config_options(self) -> GitConfig:
        return {GitConfigKey.parse(key): value for key, value in self.gitconfig.items()}

    @abc.abstractmethod
    def all_repositories(
        self,
        workspace: pathlib.Path,
    ) -> typing.Iterable[RemoteRepository]:
        raise NotImplementedError

    @abc.abstractmethod
    def select_repositories(
        self,
        workspace: pathlib.Path,
        select_self: bool,
        select_users: typing.Sequence[str],
        select_groups: typing.Sequence[str],
    ) -> typing.Iterable[RemoteRepository]:
        raise NotImplementedError


class GitHubConfig(ForgeConfig):
    type: typing.Literal["github"]

    base_url: pydantic.HttpUrl = pydantic.Field("https://api.github.com")
    login_or_token: pydantic.SecretStr = pydantic.Field()

    users: typing.Sequence[str] = pydantic.Field(default_factory=list)
    organizations: typing.Sequence[str] = pydantic.Field(default_factory=list)
    self: bool = pydantic.Field(default=True)

    def forge(self, workspace: pathlib.Path) -> GitHub:
        if self.base_url.host is None:
            raise Exception(f"Could not determine host for {self.base_url!r}")

        domain = self.base_url.host
        if domain.startswith("api."):
            domain = domain.removeprefix("api.")

        client = github.Github(
            base_url=self.base_url,
            login_or_token=self.login_or_token.get_secret_value(),
        )

        return GitHub(
            client=client,
            domain=domain,
            gitconfig=self.git_config_options(),
            workspace=workspace,
        )

    def all_repositories(
        self,
        workspace: pathlib.Path,
    ) -> typing.Iterable[RemoteRepository]:
        forge = self.forge(workspace)

        for organization in self.organizations:
            yield from forge.repositories_organization(organization)

        for user in self.users:
            yield from forge.repositories_user(user)

        if self.self:
            yield from forge.repositories_self()

    def select_repositories(
        self,
        workspace: pathlib.Path,
        select_self: bool,
        select_users: typing.Sequence[str],
        select_groups: typing.Sequence[str],
    ) -> typing.Iterable[RemoteRepository]:
        forge = self.forge(workspace)

        for organization in self.organizations:
            if organization in select_groups:
                yield from forge.repositories_organization(organization)
            else:
                forge.logger.info("Skipping GitHub organization", organization=organization)

        for user in self.users:
            if user in select_users:
                yield from forge.repositories_user(user)
            else:
                forge.logger.info("Skipping GitHub user", user=user)

        if select_self:
            yield from forge.repositories_self()
        else:
            forge.logger.info("Skipping GitHub self")


class GitLabConfig(ForgeConfig):
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

    def forge(self, workspace: pathlib.Path) -> GitLab:
        if self.base_url.host is None:
            raise Exception(f"Could not determine host for {self.base_url!r}")

        client = gitlab.Gitlab(
            url=self.base_url,
            private_token=self.private_token.get_secret_value(),
        )

        return GitLab(
            client=client,
            domain=self.base_url.host,
            gitconfig=self.git_config_options(),
            workspace=workspace,
        )

    def all_repositories(
        self,
        workspace: pathlib.Path,
    ) -> typing.Iterable[RemoteRepository]:
        forge = self.forge(workspace)

        for group in self.groups:
            yield from forge.repositories_group(group)

        for user in self.users:
            yield from forge.repositories_user(user)

        if self.self:
            yield from forge.repositories_self()

    def select_repositories(
        self,
        workspace: pathlib.Path,
        select_self: bool,
        select_users: typing.Sequence[str],
        select_groups: typing.Sequence[str],
    ) -> typing.Iterable[RemoteRepository]:
        forge = self.forge(workspace)

        for group in self.groups:
            if group in select_groups:
                yield from forge.repositories_group(group)
            else:
                forge.logger.info("Skipping GitLab group", group=group)

        for user in self.users:
            if user in select_users:
                yield from forge.repositories_user(user)
            else:
                forge.logger.info("Skipping GitLab user", user=user)

        if select_self:
            yield from forge.repositories_self()
        else:
            forge.logger.info("Skipping GitLab self")


class Config(pydantic.BaseSettings):
    workspace: pathlib.Path = pydantic.Field(env="GIT_RIVER_WORKSPACE", default=None)
    forges: typing.Mapping[str, typing.Union[GitHubConfig, GitLabConfig]] = pydantic.Field(
        default_factory=dict
    )

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

    def all_forges(self) -> typing.Sequence[ForgeConfig]:
        return [forge for forge in self.forges.values()]

    def select_forges(self, names: typing.Collection[str]) -> typing.Sequence[ForgeConfig]:
        return [forge for name, forge in self.forges.items() if name in names]


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
