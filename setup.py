#!/usr/bin/python3

import setuptools

setuptools.setup(
    name = 'python-dbusmock',
    version = '0.0.0',
    description = 'Mock D-Bus objects',

    long_description = '''With this program/Python library you can easily
create mock objects on D-Bus.  This is useful for writing tests for
software which talks to D-Bus services such as upower, systemd, ConsoleKit,
gnome-session or others, and it is hard (or impossible without root
privileges) to set the state of the real services to what you expect in
your tests.''',

    author = 'Martin Pitt',
    author_email = 'martin.pitt@ubuntu.com',
    url = 'https://launchpad.net/python-dbusmock',
    license = 'LGPL 3+',

    py_modules = ['dbus_mock'],
    test_suite = 'nose.collector',
)
