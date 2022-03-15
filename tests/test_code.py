#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import glob
import shutil
import subprocess
import sys
import unittest

pycodestyle = shutil.which('pycodestyle-3') or shutil.which('pycodestyle')
pyflakes = shutil.which('pyflakes-3') or shutil.which('pyflakes3')

if subprocess.call(['python3', '-m', 'pylint', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
    pylint = [sys.executable, '-m', 'pylint']
else:
    pylint = []

if subprocess.call(['python3', '-m', 'mypy', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
    mypy = [sys.executable, '-m', 'mypy']
else:
    mypy = []


class StaticCodeTests(unittest.TestCase):
    @unittest.skipUnless(pyflakes, 'pyflakes3 not installed')
    def test_pyflakes(self):  # pylint: disable=no-self-use
        subprocess.check_call([pyflakes, '.'])

    @unittest.skipUnless(pycodestyle, 'pycodestyle not installed')
    def test_codestyle(self):  # pylint: disable=no-self-use
        subprocess.check_call([pycodestyle, '--max-line-length=130', '--ignore=E124,E402,E731,W504', '.'])

    @unittest.skipUnless(pylint, 'pylint not installed')
    def test_pylint(self):  # pylint: disable=no-self-use
        subprocess.check_call(pylint + ['setup.py'] + glob.glob('dbusmock/*.py'))
        # signatures/arguments are not determined by us, docstrings are a bit pointless, and code repetition
        # is impractical to avoid (e.g. bluez4 and bluez5)
        subprocess.check_call(pylint +
                              ['--score=n', '--disable=missing-function-docstring,R0801',
                               '--disable=too-many-arguments,too-many-instance-attributes',
                               'dbusmock/templates/'])
        subprocess.check_call(pylint +
                              ['--score=n',
                               '--disable=missing-module-docstring,missing-class-docstring,missing-function-docstring',
                               '--disable=too-many-public-methods,too-many-lines,R0801', 'tests/'])

    @unittest.skipUnless(mypy, 'mypy not installed')
    def test_types(self):  # pylint: disable=no-self-use
        subprocess.check_call(mypy + ['setup.py', 'dbusmock/', 'tests/'])


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
