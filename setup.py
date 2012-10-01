#!/usr/bin/python3

import setuptools

setuptools.setup(
    name = 'python-dbusmock',
    version = '0.0.3',
    description = 'Mock D-Bus objects',

    author = 'Martin Pitt',
    author_email = 'martin.pitt@ubuntu.com',
    url = 'https://launchpad.net/python-dbusmock',
    license = 'LGPL 3+',

    py_modules = ['dbusmock'],
    test_suite = 'nose.collector',

    long_description = '''With this program/Python library you can easily
create mock objects on D-Bus.  This is useful for writing tests for
software which talks to D-Bus services such as upower, systemd, ConsoleKit,
gnome-session or others, and it is hard (or impossible without root
privileges) to set the state of the real services to what you expect in
your tests.''',

    classifiers = [
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        'Operating System :: Unix',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Libraries :: Python Modules',
        ],
)
