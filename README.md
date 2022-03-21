git river
=========

`git river workspace` will manage a "workspace" path you configure, cloning
and managing repositories from configured GitHub and GitLab groups.

Repositories will be organized by the domain and path of the remote GitHub
repository or GitLab project.

```
$ tree ~/workspace
~/workspace
├── github.com
│   └── datto
│       └── example
└── gitlab.com
    └── datto
        └── example
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

```bash
git-river --help
```

- `git river config` displays the current configuration.

- `git river workspace` manages the workspace path.

  Run without any subcommand, it runs all workspace subcommands except `list`
  and `fetch`.

  - `git river workspace clone` clones repositories.
  - `git river workspace configure` sets git config options.
  - `git river workspace fetch` fetches each git remote.
  - `git river workspace list` displays remote repos that will be cloned.
  - `git river workspace remotes` sets `upstream` and `origin` remotes.
  - `git river workspace tidy` deletes merged branches.

- `git river repo` manages the repository in the current directory.

  This mostly matches the features from the `workspace` subcommand.

  - `git river repo configure` sets git config options.
  - `git river repo fetch` fetches each git remote.
  - `git river repo remotes` sets `upstream` and `origin` remotes.
  - `git river repo tidy` deletes merged branches.

Configuration
-------------

Configuration is a JSON object read from `~/.config/git-river/config.json`.

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
