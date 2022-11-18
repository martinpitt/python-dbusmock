#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '''
(c) 2012 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
'''

import glob
import os
import subprocess
import sys
import unittest


@unittest.skipUnless(os.getenv("TEST_CODE", None), "$TEST_CODE not set, not running static code checks")
class StaticCodeTests(unittest.TestCase):
    def test_flake8(self):
        subprocess.check_call(['flake8'])

    def test_pylint(self):
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

    def test_types(self):
        subprocess.check_call([sys.executable, '-m', 'mypy', 'dbusmock/', 'tests/'])


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout))
