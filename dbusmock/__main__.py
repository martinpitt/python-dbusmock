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
    parser.add_argument('-t', '--template', metavar='NAME',
                        help='template to load (instead of specifying name, path, interface)')
    parser.add_argument('name', metavar='NAME', nargs='?',
                        help='D-BUS name to claim (e. g. "com.example.MyService") (if not using -t)')
    parser.add_argument('path', metavar='PATH', nargs='?',
                        help='D-BUS object path for initial/main object (if not using -t)')
    parser.add_argument('interface', metavar='INTERFACE', nargs='?',
                        help='main D-BUS interface name for initial object (if not using -t)')

    args = parser.parse_args()

    if args.template:
        if args.name or args.path or args.interface:
            parser.error('--template and specifying NAME/PATH/INTERFACE are mutually exclusive')
    else:
        if not args.name or not args.path or not args.interface:
            parser.error('Not using a template, you must specify NAME, PATH, and INTERFACE')

    return args


if __name__ == '__main__':
    import dbus.mainloop.glib
    from gi.repository import GLib

    args = parse_args()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    if args.template:
        module = dbusmock.mockobject.load_module(args.template)
        args.name = module.BUS_NAME
        args.path = module.MAIN_OBJ
        args.interface = module.MAIN_IFACE
        args.system = module.SYSTEM_BUS

    main_loop = GLib.MainLoop()
    bus = dbusmock.testcase.DBusTestCase.get_dbus(args.system)

    # quit mock when the bus is going down
    bus.add_signal_receiver(main_loop.quit, signal_name='Disconnected',
                            path='/org/freedesktop/DBus/Local',
                            dbus_interface='org.freedesktop.DBus.Local')

    bus_name = dbus.service.BusName(args.name,
                                    bus,
                                    allow_replacement=True,
                                    replace_existing=True,
                                    do_not_queue=True)

    main_object = dbusmock.mockobject.DBusMockObject(bus_name, args.path, args.interface, {}, args.logfile)

    if args.template:
        main_object.AddTemplate(args.template, None)

    dbusmock.mockobject.objects[args.path] = main_object
    main_loop.run()
