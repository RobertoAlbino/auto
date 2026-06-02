# auto

[![CI](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml)

A wrapper that runs **claude** or **codex** inside a pseudo-terminal (PTY)
and automatically answers **"yes"** every time the tool pauses to ask for
confirmation.

The only argument is which tool to run (`claude` or `codex`). No other
options and no alternative command.

## Installation

No dependencies beyond Python 3 (it uses only the standard library).

Clone the repository and put the script on your PATH:

```sh
git clone https://github.com/RobertoAlbino/auto.git
cd auto
chmod +x auto
ln -s "$PWD/auto" ~/.local/bin/auto   
```

## Usage

```sh
auto claude
auto codex
auto            # default: claude
auto update     # self-update (git pull) in the install directory
```

## Platform support

`auto` runs on **Linux and macOS**. Native **Windows is not supported**
