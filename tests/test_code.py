#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import glob
import subprocess
import sys
import unittest


checkers = {}
for checker in ['pycodestyle', 'pyflakes', 'pylint', 'mypy']:
    try:
        checkers[checker] = subprocess.check_output(
                [sys.executable, '-m', checker, '--version'], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass


class StaticCodeTests(unittest.TestCase):
    @unittest.skipUnless('pyflakes' in checkers, 'pyflakes3 not installed')
    def test_pyflakes(self):  # pylint: disable=no-self-use
        subprocess.check_call([sys.executable, '-m', 'pyflakes', '.'])

    @unittest.skipUnless('pycodestyle' in checkers, 'pycodestyle not installed')
    def test_codestyle(self):  # pylint: disable=no-self-use
        subprocess.check_call([sys.executable, '-m', 'pycodestyle',
                               '--max-line-length=130', '--ignore=E124,E402,E731,W504', '.'])

    @unittest.skipUnless('pylint' in checkers, 'pylint not installed')
    def test_pylint(self):  # pylint: disable=no-self-use
        subprocess.check_call([sys.executable, '-m', 'pylint'] + glob.glob('dbusmock/*.py'))
        # signatures/arguments are not determined by us, docstrings are a bit pointless, and code repetition
        # is impractical to avoid (e.g. bluez4 and bluez5)
        subprocess.check_call([sys.executable, '-m', 'pylint'] +
                              ['--score=n', '--disable=missing-function-docstring,R0801',
                               '--disable=too-many-arguments,too-many-instance-attributes',
                               'dbusmock/templates/'])
        subprocess.check_call([sys.executable, '-m', 'pylint'] +
                              ['--score=n',
                               '--disable=missing-module-docstring,missing-class-docstring,missing-function-docstring',
                               '--disable=too-many-public-methods,too-many-lines,too-many-statements,R0801',
                               'tests/'])

    @unittest.skipUnless('mypy' in checkers, 'mypy not installed')
    def test_types(self):  # pylint: disable=no-self-use
        subprocess.check_call([sys.executable, '-m', 'mypy', 'dbusmock/', 'tests/'])


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
