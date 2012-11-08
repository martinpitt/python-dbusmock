# coding: UTF-8
'''Main entry point for running mock server.'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import argparse

import dbus.service

import dbusmock.mockobject
import dbusmock.testcase


def parse_args():
    parser = argparse.ArgumentParser(description='mock D-BUS object')
    parser.add_argument('-s', '--system', action='store_true',
                        help='put object(s) on system bus (default: session bus)')
    parser.add_argument('-l', '--logfile', metavar='PATH',
                        help='path of log file')
    parser.add_argument('name', metavar='NAME',
                        help='D-BUS name to claim (e. g. "com.example.MyService")')
    parser.add_argument('path', metavar='PATH',
                        help='D-BUS object path for initial/main object')
    parser.add_argument('interface', metavar='INTERFACE',
                        help='main D-BUS interface name for initial object')
    return parser.parse_args()


if __name__ == '__main__':
    import dbus.mainloop.glib
    from gi.repository import GObject

    args = parse_args()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus_name = dbus.service.BusName(args.name,
                                    dbusmock.testcase.DBusTestCase.get_dbus(args.system),
                                    allow_replacement=True,
                                    replace_existing=True,
                                    do_not_queue=True)

    main_object = dbusmock.mockobject.DBusMockObject(bus_name, args.path, args.interface, {}, args.logfile)
    dbusmock.mockobject.objects[args.path] = main_object
    GObject.MainLoop().run()
