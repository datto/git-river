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

import click
import click._termui_impl
import structlog.dev
import colorama

T = typing.TypeVar("T")


def progressbar(
    iterable: typing.Iterable[T],
    event: str,
    item_show_func: typing.Callable[[T], str],
    **kwargs: str,
) -> click._termui_impl.ProgressBar[T]:
    """
    A very silly wrapper around 'click.progressbar' that matches the styling of
    'structlog.dev.ConsoleRenderer'.
    """

    level_styles = structlog.dev.ConsoleRenderer.get_default_level_styles()
    level_styles["progress"] = colorama.Fore.MAGENTA
    renderer = structlog.dev.ConsoleRenderer(level_styles=level_styles)
    template = renderer(
        logger=None,
        name="",
        event_dict={
            "progress": "%(bar)s %(info)s",
            "event": event,
            "level": "progress",
            **kwargs,
        },
    )

    return click.progressbar(
        iterable,
        bar_template=template,
        info_sep=" ",
        item_show_func=lambda x: item_show_func(x) if x is not None else None,
        show_pos=True,
        width=25,
    )
