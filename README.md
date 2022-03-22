git river
=========

`git-river` is a tool designed to make it easier to work with large
numbers of GitHub and GitLab projects and "forking" workflow that involve
pulling changes from "upstream" repositories and pushing to "downstream"
repositories. 

`git-river` will manage a "workspace" path you configure, cloning repositories
into that directory with a tree-style structure organised by domain, project
namespace, and project name.

```
$ tree ~/workspace
~/workspace
├── github.com
│   └── datto
│       └── git-river
└── gitlab.com
    └── datto
        └── git-river
```

Links
-----

* [Source code](https://github.com/datto/git-river/)
* [Packages](https://pypi.org/project/git-river/)

Installation
------------

`git-river` requires Python 3.9 or above.

```
pip3 install git-river
```

Usage
-----

Run `git-river <subcommand>`. Git's builtin aliasing also allows you to
run `git river` instead.

Before you can use `git-river` you must configure a workspace path by running
`git-river init PATH` or setting the `GIT_RIVER_WORKSPACE` environment variable.
This should point to a directory `git-river` can use to clone git repositories
into.

Several commands will attempt to discover various names, and usually have an
option flag to override discovery.

- The "upstream" remote is the first of `upstream` or `origin` that exists. Override with `--upstream`.
- The "downstream" remote is the first of `downstream` that exists. Override with `--downstream`.
- The "mainline" branch is the first of `main` or `master` that exists. Override with `--mainline`.

### Subcommands

- `git river clone URL...` clones a repository into the workspace path.

- `git river config` manages the configuration file.

  - `git river config display` prints the loaded configuration as JSON. Credentials are redacted.
  - `git river config init` creates an initial config file.
  - `git river config workspace` prints the workspace path.

- `git river forge` manages repositories listed by GitHub and GitLab.

  - `git river forge` runs the `clone` + `archived` + `configure` + `remotes` subcommands.
  - `git river forge clone` clones repositories.
  - `git river forge configure` sets git config options.
  - `git river forge fetch` fetches each git remote.
  - `git river forge list` displays remote repositories that will be cloned.
  - `git river forge remotes` sets `upstream`+`downstream` or `origin` remotes.
  - `git river forge tidy` deletes branches merged into the mainline branch.
  - `git river forge archived` lists archived repositories that exist locally.

- `git river` also provides some "loose" subcommands that work on the repository
  in the current directory, mostly matching the features from the `forge`
  subcommand.

  - `git river fetch` fetches all git remotes.
  - `git river merge` creates the merge result of all `feature/*` branches.
  - `git river tidy` deletes branches merged into the mainline branch.
  - `git river restart` rebases the current branch from the upstream remotes mainline branch.

Configuration
-------------

Configuration is a JSON object read from `~/.config/git-river/config.json`. Run
`git-river config init` to create an example configuration file.

- `path` - path to a directory to use as the "workspace".
- `forges` - a map of forges.

Forges have the following options. Only `type` is required - the default
configuration is to use the main public GitHub or GitLab domain without
authentication.

- `type` (required) - The type of the instance, either `github` or `gitlab`.
- `base_url` (optional) - Base url of the instance. Should not include a trailing slash.
  - Default for GitHub instances is `https://api.github.com`.
  - Default for GitLab instances is `https://gitlab.com`.
- `login_or_token` (optional, GitHub only) - Authentication token.
- `private_token` (optional, GitLab only) - Authentication token.
- `gitconfig` (default: `{}`) - A key-value map of git config options to set on repositories.
- `groups` (default: `[]`) - Include repositories from specific groups.
- `users` (default: `[]`) - Include repositories from specific users.
- `self` (default: `true`) - Automatically include the authenticated user's repositories.


### Example

```json
{
  "workspace": "~/Development",
  "forges": {
    "gitlab": {
      "type": "gitlab",
      "base_url": "https://gitlab.com",
      "private_token": "...",
      "groups": [],
      "users": [],
      "self": true,
      "gitconfig": {
        "user.email": "user+gitlab@example.invalid"
      }
    },
    "github": {
      "type": "github",
      "login_or_token": "...",
      "groups": [],
      "users": [],
      "gitconfig": {
        "user.email": "user+github@example.invalid"
      }
    }
  }
}
```

Development
-----------

[Poetry][poetry] is used to develop, build, and package git-river. Poetry's
[documentation][poetry/docs] describes how to install it on your OS. Once you've
installed it, create a virtual environment containing git-river and it's
dependencies with `poetry install`.

You can then run the local version of the CLI with `poetry run git-river`.

Code is formatted using [black], run with `poetry run black git_river`.

Types are checked using [mypy], run with `poetry run mypy git_river`.

Tests are written using [pytest], run with `poetry run pytest`.

```bash
# Download the project and install dependencies
git clone https://github.com/datto/git-river.git
cd git-river
poetry install

# Use the local version of the CLI
poetry run git-river ...

# Test, lint and format code
poetry run black git_river
poetry run mypy git_river
poetry run pytest
```

License
-------

Licensed under the Mozilla Public License Version 2.0.

Copyright Datto, Inc.

Authored by [Sam Clements](https://github.com/borntyping).

[black]: https://github.com/psf/black
[mypy]: https://mypy.readthedocs.io/en/stable/
[poetry/docs]: https://python-poetry.org/docs/
[poetry]: https://python-poetry.org/
[pytest]: https://docs.pytest.org/
