"""Unit tests for the `auto` PTY wrapper.

The `auto` script has no `.py` extension, so it is loaded as a module via
importlib. Only the pure, side-effect-free logic is exercised here; the
PTY/event-loop plumbing in `main()` is intentionally left to manual testing.

Run with the standard library:

    python3 -m unittest discover -v

or with pytest:

    pytest -v
"""

import importlib.util
import os
import struct
import tempfile
import unittest
from importlib.machinery import SourceFileLoader

POSIX = os.name == "posix"

if POSIX:
    import fcntl
    import pty
    import termios


def _load_auto():
    """Load the extension-less `auto` script as a module."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "auto")
    # The file has no `.py` extension, so an explicit source loader is needed.
    loader = SourceFileLoader("auto", path)
    spec = importlib.util.spec_from_loader("auto", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


auto = _load_auto()


class ResolveToolTests(unittest.TestCase):
    def test_defaults_to_claude_when_no_argument(self):
        self.assertEqual(auto.resolve_tool(["auto"]), "claude")

    def test_returns_explicit_claude(self):
        self.assertEqual(auto.resolve_tool(["auto", "claude"]), "claude")

    def test_returns_explicit_codex(self):
        self.assertEqual(auto.resolve_tool(["auto", "codex"]), "codex")

    def test_returns_unknown_tool_verbatim(self):
        # resolve_tool does not validate; validation happens in main().
        self.assertEqual(auto.resolve_tool(["auto", "vim"]), "vim")

    def test_ignores_extra_arguments(self):
        self.assertEqual(auto.resolve_tool(["auto", "codex", "extra"]), "codex")


class CompilePatternsTests(unittest.TestCase):
    def test_claude_patterns_compile(self):
        patterns = auto.compile_patterns("claude")
        self.assertEqual(len(patterns), len(auto.TOOLS["claude"]))
        for rx, keys in patterns:
            self.assertTrue(hasattr(rx, "search"))
            self.assertIsInstance(keys, bytes)

    def test_codex_patterns_compile(self):
        patterns = auto.compile_patterns("codex")
        self.assertEqual(len(patterns), len(auto.TOOLS["codex"]))

    def test_patterns_are_case_insensitive(self):
        rx, _ = auto.compile_patterns("claude")[0]
        self.assertTrue(rx.search("do you want to proceed"))

    def test_unknown_tool_raises_keyerror(self):
        with self.assertRaises(KeyError):
            auto.compile_patterns("nope")


class StripAnsiTests(unittest.TestCase):
    def test_removes_color_codes(self):
        self.assertEqual(auto.strip_ansi("\x1b[31mred\x1b[0m"), "red")

    def test_removes_cursor_positioning(self):
        self.assertEqual(auto.strip_ansi("\x1b[2J\x1b[Hhi"), "hi")

    def test_removes_carriage_returns(self):
        self.assertEqual(auto.strip_ansi("a\rb"), "ab")

    def test_removes_charset_and_mode_sequences(self):
        self.assertEqual(auto.strip_ansi("\x1b(B\x1b=text\x1b>"), "text")

    def test_keeps_plain_text_untouched(self):
        self.assertEqual(auto.strip_ansi("plain text\n"), "plain text\n")

    def test_keeps_newlines(self):
        self.assertEqual(auto.strip_ansi("a\nb"), "a\nb")


class VisibleTailTests(unittest.TestCase):
    def test_returns_only_last_lines(self):
        raw = "\n".join(str(i) for i in range(50)).encode()
        tail = auto.visible_tail(raw, tail_lines=3)
        self.assertEqual(tail, "47\n48\n49")

    def test_respects_custom_tail_lines(self):
        raw = b"a\nb\nc\nd"
        self.assertEqual(auto.visible_tail(raw, tail_lines=2), "c\nd")

    def test_returns_all_lines_when_fewer_than_limit(self):
        self.assertEqual(auto.visible_tail(b"x\ny", tail_lines=10), "x\ny")

    def test_strips_ansi_before_splitting(self):
        raw = b"\x1b[32m1. Yes\x1b[0m"
        self.assertEqual(auto.visible_tail(raw, tail_lines=1), "1. Yes")

    def test_handles_invalid_utf8_without_raising(self):
        # 0xff is not valid UTF-8; errors="replace" must keep it from crashing.
        tail = auto.visible_tail(b"\xffYes", tail_lines=1)
        self.assertIn("Yes", tail)

    def test_default_tail_lines_matches_constant(self):
        raw = ("\n".join(str(i) for i in range(auto.TAIL_LINES + 5))).encode()
        tail = auto.visible_tail(raw)
        self.assertEqual(len(tail.split("\n")), auto.TAIL_LINES)


class MatchPromptTests(unittest.TestCase):
    def setUp(self):
        self.claude = auto.compile_patterns("claude")
        self.codex = auto.compile_patterns("codex")

    def test_no_match_returns_none(self):
        self.assertIsNone(auto.match_prompt("nothing here", self.claude))

    def test_claude_proceed_returns_enter(self):
        tail = "Do you want to proceed?"
        self.assertEqual(auto.match_prompt(tail, self.claude), auto.ENTER)

    def test_claude_make_this_edit(self):
        self.assertEqual(
            auto.match_prompt("Do you want to make this edit?", self.claude),
            auto.ENTER,
        )

    def test_claude_arrow_menu(self):
        self.assertEqual(
            auto.match_prompt("❯ 1. Yes\n  2. No", self.claude), auto.ENTER
        )

    def test_claude_arrow_menu_without_number(self):
        self.assertEqual(
            auto.match_prompt("❯ Yes\n  No", self.claude), auto.ENTER
        )

    def test_claude_numbered_menu_without_arrow(self):
        self.assertEqual(
            auto.match_prompt("1. Yes   2. No", self.claude), auto.ENTER
        )

    def test_claude_multiline_numbered_menu_without_arrow(self):
        self.assertEqual(
            auto.match_prompt("1. Yes\n2. No", self.claude), auto.ENTER
        )

    def test_codex_allow_question(self):
        self.assertEqual(
            auto.match_prompt("Allow this command?", self.codex), auto.ENTER
        )

    def test_codex_approve(self):
        self.assertEqual(
            auto.match_prompt("Approve changes", self.codex), auto.ENTER
        )

    def test_codex_arrow_menu_without_number(self):
        self.assertEqual(
            auto.match_prompt("› Yes\n  No", self.codex), auto.ENTER
        )

    def test_codex_multiline_numbered_menu_without_arrow(self):
        self.assertEqual(
            auto.match_prompt("1. Yes\n2. No", self.codex), auto.ENTER
        )

    def test_codex_yn_sends_y_enter(self):
        self.assertEqual(auto.match_prompt("continue? (y/n)", self.codex), b"y\r")

    def test_codex_bracketed_yn_sends_y_enter(self):
        self.assertEqual(auto.match_prompt("continue? [y/N]", self.codex), b"y\r")

    def test_match_is_case_insensitive(self):
        self.assertEqual(
            auto.match_prompt("DO YOU WANT TO PROCEED?", self.claude), auto.ENTER
        )

    def test_first_matching_pattern_wins(self):
        # Both an arrow menu and a (y/n) appear; codex lists Allow/Approve/arrow
        # before (y/n), so a screen with an arrow menu yields ENTER, not b"y\r".
        tail = "❯ 1. Yes\n  2. No\n(y/n)"
        self.assertEqual(auto.match_prompt(tail, self.codex), auto.ENTER)

    def test_empty_patterns_returns_none(self):
        self.assertIsNone(auto.match_prompt("Do you want to proceed?", []))


@unittest.skipUnless(POSIX, "PTY/termios winsize is POSIX-only")
class WinsizeTests(unittest.TestCase):
    def _closed_fd(self):
        """Return a file descriptor number that has already been closed."""
        master_fd, slave_fd = pty.openpty()
        os.close(master_fd)
        os.close(slave_fd)
        return slave_fd

    def test_get_winsize_on_bad_fd_returns_default(self):
        # A closed fd makes ioctl raise OSError; get_winsize must swallow it.
        self.assertEqual(auto.get_winsize(self._closed_fd()), (24, 80))

    def test_set_winsize_on_bad_fd_does_not_raise(self):
        # Should silently ignore the OSError from a closed fd.
        auto.set_winsize(self._closed_fd(), 30, 100)

    def test_set_then_get_roundtrip_on_pty(self):
        master_fd, slave_fd = pty.openpty()
        try:
            auto.set_winsize(slave_fd, 40, 120)
            self.assertEqual(auto.get_winsize(slave_fd), (40, 120))
        finally:
            os.close(master_fd)
            os.close(slave_fd)

    def test_get_winsize_reads_ioctl_value(self):
        master_fd, slave_fd = pty.openpty()
        try:
            fcntl.ioctl(
                slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 12, 34, 0, 0)
            )
            self.assertEqual(auto.get_winsize(slave_fd), (12, 34))
        finally:
            os.close(master_fd)
            os.close(slave_fd)


class InstallDirTests(unittest.TestCase):
    def test_returns_directory_of_script(self):
        here = os.path.dirname(os.path.abspath(__file__))
        self.assertEqual(auto.install_dir(), here)

    def test_resolves_symlinks_to_real_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = os.path.join(tmp, "checkout")
            os.mkdir(real_dir)
            real = os.path.join(real_dir, "auto")
            with open(real, "w"):
                pass
            link = os.path.join(tmp, "auto-link")
            os.symlink(real, link)
            # install_dir must follow the symlink to the real checkout dir.
            # Normalize the expected path too: on macOS the temp root itself
            # contains symlinked components (e.g. /tmp -> /private/tmp).
            self.assertEqual(auto.install_dir(link), os.path.realpath(real_dir))


class UpdateTests(unittest.TestCase):
    def _git_checkout(self, tmp):
        os.mkdir(os.path.join(tmp, ".git"))
        return tmp

    def test_runs_git_pull_ff_only_in_repo(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._git_checkout(tmp)
            code = auto.update(repo=repo, runner=lambda cmd: calls.append(cmd) or 0)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [["git", "-C", repo, "pull", "--ff-only"]])

    def test_propagates_git_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._git_checkout(tmp)
            code = auto.update(repo=repo, runner=lambda cmd: 5)
        self.assertEqual(code, 5)

    def test_non_git_directory_returns_1_without_running_git(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            code = auto.update(repo=tmp, runner=lambda cmd: calls.append(cmd) or 0)
        self.assertEqual(code, 1)
        self.assertEqual(calls, [])

    def test_defaults_repo_to_install_dir(self):
        captured = {}

        def fake_runner(cmd):
            captured["cmd"] = cmd
            return 0

        original = auto.install_dir
        with tempfile.TemporaryDirectory() as tmp:
            self._git_checkout(tmp)
            auto.install_dir = lambda *a, **k: tmp  # force the default lookup
            try:
                code = auto.update(runner=fake_runner)
            finally:
                auto.install_dir = original
        self.assertEqual(code, 0)
        # With repo omitted, update() must target the install_dir() result.
        self.assertEqual(captured["cmd"], ["git", "-C", tmp, "pull", "--ff-only"])


class ConstantsTests(unittest.TestCase):
    def test_enter_is_carriage_return(self):
        self.assertEqual(auto.ENTER, b"\r")

    def test_known_tools(self):
        self.assertEqual(set(auto.TOOLS), {"claude", "codex"})

    def test_buffer_limit_positive(self):
        self.assertGreater(auto.BUFFER_LIMIT, 0)

    def test_idle_secs_positive(self):
        self.assertGreater(auto.IDLE_SECS, 0)


if __name__ == "__main__":
    unittest.main()
