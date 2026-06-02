# auto

[![CI](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertoAlbino/auto/actions/workflows/ci.yml)

A wrapper that runs **claude** or **codex** inside a pseudo-terminal (PTY)
and automatically answers **"yes"** every time the tool pauses to ask for
confirmation.

The only argument is which tool to run (`claude` or `codex`). No other
options and no alternative command.

## Why a PTY (and not a pipe)?

`claude` and `codex` are interactive TUIs: they detect whether they are
attached to a real terminal and, outside of a TTY, change their behavior or
refuse to run in interactive mode. That's why a pipe **does not work** — you
have to run the tool inside a PTY, which is what this program does. On top of
that, the confirmations are **arrow-key selection menus** ("❯ 1. Yes / 2. No"),
not a plain-text `(y/n)`. Since the "Yes" option is usually pre-highlighted,
answering = sending **Enter**.

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
