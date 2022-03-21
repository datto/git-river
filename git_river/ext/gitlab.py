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

import gitlab.v4.objects


GitLabProject = typing.Union[
    gitlab.v4.objects.GroupProject,
    gitlab.v4.objects.Project,
    gitlab.v4.objects.UserProject,
]


class ForkedFromProject(typing.TypedDict):
    path_with_namespace: str
    ssh_url_to_repo: str


def forked_from_project(project: GitLabProject) -> typing.Optional[ForkedFromProject]:
    return getattr(project, "forked_from_project", None)
