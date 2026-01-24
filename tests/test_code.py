# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Martin Pitt"
__copyright__ = """
(c) 2012 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""

import glob
import importlib.util
import os
import subprocess
import sys
import unittest


@unittest.skipIf(
    os.getenv("SKIP_STATIC_CHECKS", "0") == "1", "$SKIP_STATIC_CHECKS set, not running static code checks"
)
class StaticCodeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pylint"), "pylint not available, skipping")
    def test_pylint(self):
        subprocess.check_call([sys.executable, "-m", "pylint", *glob.glob("dbusmock/*.py")])
        # signatures/arguments are not determined by us, docstrings are a bit pointless, and code repetition
        # is impractical to avoid (e.g. bluez4 and bluez5)
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pylint",
                "--score=n",
                "--disable=missing-function-docstring,R0801",
                "--disable=too-many-arguments,too-many-instance-attributes",
                "--disable=too-few-public-methods",
                "dbusmock/templates/",
            ]
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pylint",
                "--score=n",
                "--disable=missing-module-docstring,missing-class-docstring",
                "--disable=missing-function-docstring",
                "--disable=too-many-public-methods,too-many-lines,too-many-statements,R0801",
                "--disable=fixme",
                "tests/",
            ]
        )

    @unittest.skipUnless(importlib.util.find_spec("mypy"), "mypy not available, skipping")
    def test_types(self):
        subprocess.check_call([sys.executable, "-m", "mypy", "dbusmock/", "tests/"])

    def test_ruff(self):
        try:
            subprocess.check_call(["ruff", "check", "--no-cache", "."])
        except FileNotFoundError:
            self.skipTest("ruff not available, skipping")

    def test_black(self):
        try:
            subprocess.check_call(["black", "--check", "--diff", "."])
        except FileNotFoundError:
            self.skipTest("black not available, skipping")


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
