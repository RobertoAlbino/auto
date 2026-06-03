# auto

[![CI](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml)

A wrapper that runs **claude** or **codex** inside a pseudo-terminal and
automatically answers **"yes"** every time the tool pauses to ask for
confirmation.

## Installation

Needs only Python 3. Clone the repo and run the
installer for your platform.

```sh
git clone https://github.com/RobertoAlbino/auto.git
cd auto
./install.sh        # Linux / macOS
./install.bat       # Windows
```

## Usage

```sh
auto claude
auto codex
auto            # default: claude
auto update     # self-update (git pull) in the install directory
auto --version  # print the running version and exit
```

On startup `auto` prints its version (e.g. `auto 0.1.1`) to stderr before
handing the terminal over to the tool.

## Versioning

The version lives in the `__version__` string at the top of `auto`. A
`pre-commit` hook (in `.githooks/`) bumps the patch number on **every commit**
and re-stages `auto`, so the committed version is always one ahead. `install.sh`
enables the hook automatically; to enable it by hand run:

```sh
git config core.hooksPath .githooks
```

## Platform support

auto Works on **Linux**, **macOS**, and **Windows**