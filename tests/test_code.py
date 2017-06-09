#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import sys
import unittest
import subprocess
import shutil


pycodestyle = shutil.which('pycodestyle') or shutil.which('pycodestyle-3')


class StaticCodeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('pyflakes'), 'pyflakes not installed')
    def test_pyflakes(self):
        pyflakes = subprocess.Popen(['pyflakes', '.'], stdout=subprocess.PIPE,
                                    universal_newlines=True)
        (out, err) = pyflakes.communicate()
        self.assertEqual(pyflakes.returncode, 0, out)

    @unittest.skipUnless(pycodestyle, 'pycodestyle not installed')
    def test_codestyle(self):
        pep8 = subprocess.Popen([pycodestyle, '--max-line-length=130', '--ignore=E124,E402,E731', '.'],
                                stdout=subprocess.PIPE, universal_newlines=True)
        (out, err) = pep8.communicate()
        self.assertEqual(pep8.returncode, 0, out)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
