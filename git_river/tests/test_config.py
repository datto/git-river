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

import pathlib

import pytest
import git_river.repository


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.invalid/example-group/example-name.git",
        "git@gitlab.invalid:example-group/example-name.git",
    ],
)
def test_repository_from_url(tmp_path: pathlib.Path, url: str) -> None:
    repo = git_river.repository.RemoteRepository.from_url(workspace=tmp_path, url=url)

    assert repo.clone_url == url
    assert repo.group == "gitlab.invalid"
    assert repo.name == "example-name"
    assert repo.path == tmp_path / repo.group / "example-group" / "example-name"
