# ---------------------------------------------------------------------------
# chargecap - keep an always-plugged-in phone inside a charge window
#
# Licence: General Pleasure League (GPL) 1.0
#          https://github.com/fanzu8/General-Pleasure-League
#
#          You are the general of your own life, the master of your own fate:
#          no restrictions, no compulsions - use it, change it, share it, and
#          let pleasure be your primary guide.  Just be happy.
# ---------------------------------------------------------------------------

"""The packaging contract: where things are installed, and what the scripts do.

These are the pieces a refactor can quietly break -- a renamed file, a missing
systemd argument, an uninstall that forgets to release the charger.
"""
import os
import py_compile
import re
import subprocess
import unittest

from tests.helpers import ROOT

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(HERE, name)) as f:
        return f.read()


class SyntaxTest(unittest.TestCase):
    def test_scripts_compile(self):
        for name in ("chargecap", "daemon.py", "tools/gtk-preview.py",
                     "tools/make-icons.py"):
            with self.subTest(name):
                py_compile.compile(os.path.join(HERE, name), doraise=True)

    def test_shell_scripts_are_valid(self):
        for name in ("install.sh", "uninstall.sh"):
            with self.subTest(name):
                done = subprocess.run(["sh", "-n", os.path.join(HERE, name)],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)

    def test_every_test_module_is_collected(self):
        found = sorted(f for f in os.listdir(os.path.join(HERE, "tests"))
                       if f.startswith("test_") and f.endswith(".py"))
        self.assertIn("test_daemon.py", found)
        self.assertIn("test_gui.py", found)
        self.assertIn("test_scripts.py", found)


class LicenceTest(unittest.TestCase):
    """Every source and test file says what it is and under what licence.

    The header is separated from what follows -- and from a shebang before it --
    by a blank line, so it reads as a header instead of blending into the file.
    """

    SOURCES = ("chargecap", "daemon.py", "install.sh", "uninstall.sh",
               "tools/gtk-preview.py", "tools/make-icons.py")
    TESTS = ("tests/__init__.py", "tests/helpers.py", "tests/test_daemon.py",
             "tests/test_gui.py", "tests/test_scripts.py")

    def lines_of(self, name):
        with open(os.path.join(HERE, name)) as f:
            return f.readlines()

    def test_sources_start_with_a_shebang_and_the_header(self):
        for name in self.SOURCES:
            with self.subTest(name):
                lines = self.lines_of(name)
                self.assertTrue(lines[0].startswith("#!"), name)
                head = "".join(lines[:14])
                self.assertIn("General Pleasure League (GPL) 1.0", head)
                self.assertIn("fanzu8/General-Pleasure-League", head)
                self.assertIn("general of your own life", head)
                self.assertIn("Just be happy", head)

    def test_tests_carry_the_header_as_well(self):
        for name in self.TESTS:
            with self.subTest(name):
                head = "".join(self.lines_of(name)[:14])
                self.assertIn("General Pleasure League (GPL) 1.0", head)
                self.assertIn("general of your own life", head)

    def test_the_header_is_surrounded_by_blank_lines(self):
        for name in self.SOURCES + self.TESTS:
            with self.subTest(name):
                lines = self.lines_of(name)
                start = next(i for i, l in enumerate(lines)
                             if l.startswith("# ---"))
                end = next(i for i in range(start + 1, len(lines))
                           if lines[i].startswith("# ---"))
                if start > 0:            # e.g. after a shebang
                    self.assertEqual(lines[start - 1].strip(), "", name)
                self.assertEqual(lines[end + 1].strip(), "", name)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.install = read("install.sh")
        self.uninstall = read("uninstall.sh")

    def test_installs_to_the_documented_places(self):
        for target in ("/usr/local/bin/chargecap",
                       "/usr/local/lib/chargecap/daemon.py",
                       "/etc/systemd/system/chargecap.service",
                       "/usr/share/applications/org.postmarketos.Chargecap.desktop"):
            self.assertIn(target, self.install, target)

    def test_install_enables_the_service(self):
        self.assertIn("systemctl daemon-reload", self.install)
        self.assertIn("systemctl enable --now chargecap.service",
                      self.install)

    def test_uninstall_removes_the_same_things(self):
        for target in ("/etc/systemd/system/chargecap.service",
                       "/usr/local/bin/chargecap",
                       "/usr/local/lib/chargecap",
                       "/usr/share/applications/org.postmarketos.Chargecap.desktop",
                       "/var/lib/chargecap",
                       "/run/chargecap",
                       "/home/user/.config/chargecap"):
            self.assertIn(target, self.uninstall, target)

    def test_uninstall_releases_the_charger(self):
        """Otherwise the phone would stay stuck at the limit (or on a small
        input current) after the app is gone."""
        self.assertIn("/sys/class/power_supply/pmi8998-charger/status",
                      self.uninstall)
        self.assertIn("/sys/class/power_supply/pmi8998-charger/current_max",
                      self.uninstall)
        self.assertIn("constant_charge_current_max", self.uninstall)


class UnitFileTest(unittest.TestCase):
    def setUp(self):
        self.unit = read("chargecap.service")

    def test_runs_the_installed_daemon_with_the_documented_paths(self):
        self.assertIn("ExecStart=/usr/bin/python3 "
                      "/usr/local/lib/chargecap/daemon.py", self.unit)
        for arg in ("--config /var/lib/chargecap/config.json",
                    "--request /home/user/.config/chargecap/request.json",
                    "--state /run/chargecap/state.json"):
            self.assertIn(arg, self.unit, arg)

    def test_restarts_on_failure_and_starts_at_boot(self):
        self.assertIn("Restart=always", self.unit)
        self.assertIn("WantedBy=multi-user.target", self.unit)


class DesktopEntryTest(unittest.TestCase):
    def setUp(self):
        self.entry = read("org.postmarketos.Chargecap.desktop")

    def test_launches_the_installed_gui(self):
        self.assertIn("Exec=/usr/local/bin/chargecap", self.entry)

    def test_is_named_chargecap_and_diandian(self):
        """chargecap by default, 电电 when the system is Chinese: the launcher
        resolves Name[zh_CN] itself, so no install time logic is involved."""
        self.assertIn("Name=chargecap", self.entry)
        self.assertIn("Name[zh_CN]=电电", self.entry)
        # the icon file name stays the application id, never the display name
        self.assertIn("Icon=org.postmarketos.Chargecap", self.entry)

    def test_uses_its_own_icon_named_after_the_app_id(self):
        """GNOME matches the icon by file name, so it has to be the app id."""
        self.assertIn("Icon=org.postmarketos.Chargecap", self.entry)
        icon = os.path.join(HERE, "icons", "org.postmarketos.Chargecap.svg")
        self.assertTrue(os.path.exists(icon), "the icon file is missing")
        self.assertIn("/usr/share/icons/hicolor/scalable/apps/"
                      "org.postmarketos.Chargecap.svg", read("install.sh"))
        self.assertIn("/usr/share/icons/hicolor/scalable/apps/"
                      "org.postmarketos.Chargecap.svg", read("uninstall.sh"))

    def test_comment_is_localised(self):
        self.assertIn("Comment=", self.entry)
        self.assertIn("Comment[zh_CN]=设置电池充电上下限，并可插电时禁止休眠",
                      self.entry)


class DocsTest(unittest.TestCase):
    def test_every_document_reference_exists(self):
        """A renamed or deleted file must not stay referenced in the READMEs."""
        import re
        for name in ("README.md", "README.zh.md"):
            with open(os.path.join(HERE, name)) as f:
                body = f.read()
            for path in re.findall(r"(?:docs|icons)/[A-Za-z0-9._-]+", body):
                self.assertTrue(os.path.exists(os.path.join(HERE, path)),
                                f"{name} refers to {path}, which is missing")


class SecretTest(unittest.TestCase):
    """Nothing in the repository may look like a credential.

    The code, the docs and the commit messages are public; a token that lands
    here by accident is a token to revoke.
    """

    PATTERNS = (r"gh[pousr]_[A-Za-z0-9]{20,}",
                r"github_pat_[A-Za-z0-9_]{20,}",
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

    def test_no_credentials_in_the_repository(self):
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith((".gif", ".png", ".pyc")):
                    continue
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    blob = f.read().decode("utf-8", "replace")
                for pattern in self.PATTERNS:
                    self.assertIsNone(
                        re.search(pattern, blob),
                        f"{path} looks like it contains a credential")


class WorkflowTest(unittest.TestCase):
    """CI has to keep running these tests, and it must not need a phone."""

    def test_ci_workflow_runs_the_suite(self):
        path = os.path.join(HERE, ".github", "workflows", "tests.yml")
        self.assertTrue(os.path.exists(path), "no CI workflow")
        with open(path) as f:
            body = f.read()
        self.assertIn("python3 -m unittest", body)
        self.assertNotIn("systemctl", body)

    def test_ci_cancels_superseded_runs(self):
        """A newer push should cancel the older test run, not queue behind it."""
        with open(os.path.join(HERE, ".github", "workflows", "tests.yml")) as f:
            body = f.read()
        self.assertIn("concurrency:", body)
        self.assertIn("cancel-in-progress: true", body)


if __name__ == "__main__":
    unittest.main()
