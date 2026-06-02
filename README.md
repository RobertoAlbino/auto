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
ln -s "$PWD/auto" ~/.local/bin/auto   # or /usr/local/bin
```

> The destination directory (`~/.local/bin`) must be on your `PATH`.

## Usage

```sh
auto claude
auto codex
auto            # default: claude
auto update     # self-update (git pull) in the install directory
```

### Updating

Since `auto` is installed from a git checkout, `auto update` simply runs
`git pull --ff-only` in the directory where the real script lives (symlinks on
your PATH are resolved first). It is fast-forward only, so it never creates a
merge commit or clobbers local changes — if the pull can't fast-forward, git
says so and nothing is changed. If the install directory is not a git checkout,
`auto update` prints a message and exits non-zero instead of doing anything.

## How it works

1. Launches the chosen tool with `pty.fork()` (a virtual terminal).
2. Relays input/output between your terminal and the child — you still see the
   TUI and can type normally.
3. Keeps a buffer of the last lines on screen, strips ANSI codes and, after a
   short idle period, compares them against the known prompt patterns.
4. A pattern matched → it sends **Enter** to the child (selecting the
   highlighted "Yes" option).
5. Propagates `SIGWINCH` (resize) and the child's **exit code**.

The patterns live in `TOOLS`, at the top of the `auto` script. If an update to
claude or codex changes the TUI text/layout, adjust the regexes there.

## ⚠️ Security

Auto-accepting **everything** also bypasses confirmations for **destructive
actions** (deleting files, running dangerous commands). Recommendations:

- Use it in a directory/sandbox with nothing critical.
- Consider the native flags, which are more predictable than scraping the TUI:
  - Claude: `claude --dangerously-skip-permissions` (or `--permission-mode acceptEdits`)
  - Codex: `codex --dangerously-bypass-approvals-and-sandbox` (or `--ask-for-approval never --full-auto`)

## Limitations

- Detection depends on the TUI text/layout; updates to claude or codex may
  require adjusting the regexes in `TOOLS`.
- For menus with several options ("Yes" / "Yes, and don't ask again" / "No"),
  it sends Enter (selecting the highlighted option).

## Tests

The project ships with a unit-test suite (standard library only) that covers
the pure logic: tool resolution, pattern compilation, ANSI stripping, tail
extraction, prompt matching and the window-size helpers.

```sh
python3 -m unittest discover -v      # using the standard library
pytest -v                            # if you have pytest installed
```
