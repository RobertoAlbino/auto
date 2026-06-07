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

    def test_claude_boxed_arrow_menu(self):
        # claude draws confirmations inside a box, so the menu line starts with
        # the border `│ ` before the arrow. The generic fallback must still
        # match even when the question text is not a tool-specific phrase.
        tail = (
            "│ Save file to disk?        │\n"
            "│ ❯ 1. Yes                  │\n"
            "│   2. No                   │"
        )
        self.assertEqual(auto.match_prompt(tail, self.claude), auto.ENTER)

    def test_claude_boxed_numbered_menu(self):
        tail = "│ 1. Yes   │\n│ 2. No    │"
        self.assertEqual(auto.match_prompt(tail, self.claude), auto.ENTER)

    def test_claude_multiline_numbered_menu_without_arrow(self):
        self.assertEqual(
            auto.match_prompt("1. Yes\n2. No", self.claude), auto.ENTER
        )

    def test_codex_allow_question(self):
        self.assertEqual(
            auto.match_prompt("Allow this command?", self.codex), auto.ENTER
        )

    def test_codex_run_command_question(self):
        tail = (
            "Would you like to run the following command?\n"
            " \n"
            "  Reason: Permite rodar os testes de integração com Testcontainers "
            "acessando o Docker local?\n"
            " \n"
            "  $ ./mvnw test\n"
            " \n"
            "› 1. Yes, proceed (y)\n"
            "  2. Yes, and don't ask again for commands that start with "
            "`./mvnw test` (p)\n"
            "  3. No, and tell Codex what to do differently (esc)"
        )
        self.assertEqual(auto.match_prompt(tail, self.codex), auto.ENTER)

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

    def test_ex_returns_keys_and_matched_text(self):
        keys, sig = auto.match_prompt_ex("Do you want to proceed?", self.claude)
        self.assertEqual(keys, auto.ENTER)
        self.assertEqual(sig, "Do you want to proceed")

    def test_ex_returns_none_without_a_match(self):
        self.assertIsNone(auto.match_prompt_ex("nothing here", self.claude))

    def test_ex_signature_ignores_surrounding_noise(self):
        # The matched text is the same whether or not a spinner line follows,
        # so it is a stable identity for the prompt across repaints.
        a = auto.match_prompt_ex("❯ 1. Yes\n  2. No", self.claude)
        b = auto.match_prompt_ex("❯ 1. Yes\n  2. No\n  / working", self.claude)
        self.assertEqual(a[1], b[1])


class AnswererTests(unittest.TestCase):
    """The state machine that decides what to send and when to re-send."""

    def setUp(self):
        self.patterns = auto.compile_patterns("claude")
        # Small, explicit windows so the tests can drive time by hand.
        self.a = auto.Answerer(
            self.patterns, stable_secs=0.4, retry_secs=1.0, max_retries=2
        )
        self.prompt = "Do you want to proceed?"

    def _answer(self, tail, t0=0.0):
        """Drive a prompt from first sighting to its answer; return the keys."""
        self.assertIsNone(self.a.consider(tail, now=t0))     # starts the window
        return self.a.consider(tail, now=t0 + self.a.stable_secs)

    def test_answers_once_prompt_is_stable(self):
        # First sighting only starts the stability window; the answer comes
        # once the prompt has stayed up for stable_secs.
        self.assertIsNone(self.a.consider(self.prompt, now=0.0))
        self.assertIsNone(self.a.consider(self.prompt, now=0.3))
        self.assertEqual(self.a.consider(self.prompt, now=0.4), auto.ENTER)

    def test_returns_none_when_no_prompt(self):
        self.assertIsNone(self.a.consider("just some output", now=0.0))

    def test_does_not_reanswer_the_same_prompt(self):
        self.assertEqual(self._answer(self.prompt), auto.ENTER)
        self.assertIsNone(self.a.consider(self.prompt, now=0.5))

    def test_answers_through_a_churning_spinner(self):
        # The menu holds still while a spinner line below it animates every
        # frame: the screen never goes quiet, but the matched prompt text does
        # not change, so the prompt is still answered exactly once.
        frames = [
            "Do you want to proceed?\n❯ 1. Yes\n  2. No\n  {} working".format(c)
            for c in "|/-\\|/-\\"
        ]
        answers = []
        for i, frame in enumerate(frames):
            keys = self.a.consider(frame, now=i * 0.15)
            if keys is not None:
                answers.append(keys)
        self.assertEqual(answers, [auto.ENTER])

    def test_answers_a_different_prompt_after_the_first(self):
        self.assertEqual(self._answer("Do you want to make this edit?"), auto.ENTER)
        # A genuinely different prompt restarts the window and is answered.
        self.assertIsNone(self.a.consider(self.prompt, now=2.0))
        self.assertEqual(self.a.consider(self.prompt, now=2.5), auto.ENTER)

    def test_needs_tick_tracks_outstanding_work(self):
        self.assertFalse(self.a.needs_tick())
        self.a.consider(self.prompt, now=0.0)
        # A tracked-but-unanswered prompt needs ticking to close its window.
        self.assertTrue(self.a.needs_tick())
        # A screen with no prompt clears the state.
        self.a.consider("done", now=0.1)
        self.assertFalse(self.a.needs_tick())

    def test_resends_when_prompt_lingers_after_answering(self):
        self.assertEqual(self._answer(self.prompt), auto.ENTER)
        # Still on screen well past the retry window: the keystroke was likely
        # dropped mid-redraw, so re-send.
        self.assertEqual(self.a.consider(self.prompt, now=1.5), auto.ENTER)

    def test_does_not_resend_before_retry_window(self):
        self.assertEqual(self._answer(self.prompt), auto.ENTER)
        self.assertIsNone(self.a.consider(self.prompt, now=0.9))

    def test_resend_stops_after_max_retries(self):
        self.assertEqual(self._answer(self.prompt), auto.ENTER)
        self.assertEqual(self.a.consider(self.prompt, now=1.5), auto.ENTER)
        self.assertEqual(self.a.consider(self.prompt, now=2.6), auto.ENTER)
        # Two re-sends is the cap; a genuinely stuck prompt is left alone.
        self.assertFalse(self.a.needs_tick())
        self.assertIsNone(self.a.consider(self.prompt, now=3.7))

    def test_clears_state_when_prompt_disappears(self):
        self.assertEqual(self._answer(self.prompt), auto.ENTER)
        # The prompt is gone (answer landed): nothing to re-send, state clears.
        self.assertIsNone(self.a.consider("command output", now=1.5))
        self.assertFalse(self.a.needs_tick())

    def test_reset_forgets_the_tracked_prompt(self):
        self.a.consider(self.prompt, now=0.0)
        self.a.reset()
        self.assertFalse(self.a.needs_tick())
        # After a reset the same prompt is tracked fresh again.
        self.assertEqual(self._answer(self.prompt, t0=0.1), auto.ENTER)


class DebugCaptureTests(unittest.TestCase):
    """The opt-in AUTO_DEBUG sink that records what auto sees per screen."""

    def setUp(self):
        self.patterns = auto.compile_patterns("claude")

    def test_append_debug_records_tail_and_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log")
            match = auto.match_prompt_ex("Do you want to proceed?", self.patterns)
            auto.append_debug(path, 1.5, "Do you want to proceed?", match)
            with open(path, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("MATCH", text)
        self.assertIn("Do you want to proceed", text)

    def test_append_debug_records_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log")
            auto.append_debug(path, 0.0, "some garbled screen", None)
            with open(path, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("NO MATCH", text)

    def test_append_debug_swallows_bad_path(self):
        # A directory that does not exist must not raise into the event loop.
        auto.append_debug("/no/such/dir/log", 0.0, "x", None)

    def test_answerer_logs_only_when_tail_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log")
            a = auto.Answerer(self.patterns, debug_path=path)
            a.consider("Do you want to proceed?", now=0.0)
            a.consider("Do you want to proceed?", now=0.1)  # unchanged: no log
            a.consider("a different screen", now=0.2)
            with open(path, encoding="utf-8") as f:
                blocks = f.read().count("-----") // 2
        self.assertEqual(blocks, 2)

    def test_answerer_without_debug_writes_nothing(self):
        # Default construction (no AUTO_DEBUG) must not touch the filesystem.
        a = auto.Answerer(self.patterns)
        self.assertIsNone(a.consider("Do you want to proceed?", now=0.0))


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


class BumpVersionTests(unittest.TestCase):
    def test_bumps_patch_by_default(self):
        self.assertEqual(auto.bump_version("1.2.3"), "1.2.4")

    def test_bumps_minor_and_resets_patch(self):
        self.assertEqual(auto.bump_version("1.2.3", "minor"), "1.3.0")

    def test_bumps_major_and_resets_minor_and_patch(self):
        self.assertEqual(auto.bump_version("1.2.3", "major"), "2.0.0")

    def test_unknown_part_raises_valueerror(self):
        with self.assertRaises(ValueError):
            auto.bump_version("1.2.3", "nope")


class BumpSourceTests(unittest.TestCase):
    def _write(self, tmp, body):
        path = os.path.join(tmp, "auto")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return path

    def test_increments_version_in_file_and_returns_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, 'x = 1\n__version__ = "0.4.9"\ny = 2\n')
            self.assertEqual(auto.bump_source(path), "0.4.10")
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), 'x = 1\n__version__ = "0.4.10"\ny = 2\n')

    def test_honours_part_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, '__version__ = "1.0.0"\n')
            self.assertEqual(auto.bump_source(path, "major"), "2.0.0")

    def test_missing_version_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "no version here\n")
            with self.assertRaises(ValueError):
                auto.bump_source(path)


class ConstantsTests(unittest.TestCase):
    def test_enter_is_carriage_return(self):
        self.assertEqual(auto.ENTER, b"\r")

    def test_version_is_a_semver_string(self):
        self.assertRegex(auto.__version__, r"^\d+\.\d+\.\d+$")

    def test_known_tools(self):
        self.assertEqual(set(auto.TOOLS), {"claude", "codex"})

    def test_buffer_limit_positive(self):
        self.assertGreater(auto.BUFFER_LIMIT, 0)

    def test_idle_secs_positive(self):
        self.assertGreater(auto.IDLE_SECS, 0)


if __name__ == "__main__":
    unittest.main()
