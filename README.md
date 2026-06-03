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
install.bat         # Windows (then open a new terminal)
```

## Usage

```sh
auto claude
auto codex
auto            # default: claude
auto update     # self-update (git pull) in the install directory
```

## Platform support

auto Works on **Linux**, **macOS**, and **Windows**