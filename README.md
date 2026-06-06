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

## Troubleshooting a missed prompt

If `auto` leaves a confirmation sitting unanswered, set `AUTO_DEBUG` to a file
path before launching: every screen `auto` inspects is appended there with
whether it matched a prompt. That captures exactly what the wrapped tool sent
through the PTY, which is what is needed to tell a regex gap apart from a
garbled / partial redraw.

```sh
AUTO_DEBUG=/tmp/auto.log auto claude
# reproduce the missed prompt, then inspect /tmp/auto.log
```

## Platform support

auto Works on **Linux**, **macOS**, and **Windows**
