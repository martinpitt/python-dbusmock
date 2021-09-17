# coding: UTF-8
'''Main entry point for running mock server.'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import argparse
import json
import sys

import dbusmock.mockobject
import dbusmock.testcase


def parse_args():
    '''Parse command line arguments'''

    parser = argparse.ArgumentParser(description='mock D-Bus object')
    parser.add_argument('-s', '--system', action='store_true',
                        help="put object(s) on system bus (default: session bus or template's SYSTEM_BUS flag)")
    parser.add_argument('--session', action='store_true',
                        help="put object(s) on session bus (default without template; overrides template's SYSTEM_BUS flag)")
    parser.add_argument('-l', '--logfile', metavar='PATH',
                        help='path of log file')
    parser.add_argument('-t', '--template', metavar='NAME',
                        help='template to load (instead of specifying name, path, interface)')
    parser.add_argument('name', metavar='NAME', nargs='?',
                        help='D-Bus name to claim (e. g. "com.example.MyService") (if not using -t)')
    parser.add_argument('path', metavar='PATH', nargs='?',
                        help='D-Bus object path for initial/main object (if not using -t)')
    parser.add_argument('interface', metavar='INTERFACE', nargs='?',
                        help='main D-Bus interface name for initial object (if not using -t)')
    parser.add_argument('-m', '--is-object-manager', action='store_true',
                        help='automatically implement the org.freedesktop.DBus.ObjectManager interface')
    parser.add_argument('-p', '--parameters',
                        help='JSON dictionary of parameters to pass to the template')

    arguments = parser.parse_args()

    if arguments.template:
        if arguments.name or arguments.path or arguments.interface:
            parser.error('--template and specifying NAME/PATH/INTERFACE are mutually exclusive')
    else:
        if not arguments.name or not arguments.path or not arguments.interface:
            parser.error('Not using a template, you must specify NAME, PATH, and INTERFACE')

    if arguments.system and arguments.session:
        parser.error('--system and --session are mutually exclusive')

    return arguments


if __name__ == '__main__':
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib

    args = parse_args()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    system_bus = args.system
    if args.template:
        module = dbusmock.mockobject.load_module(args.template)
        args.name = module.BUS_NAME
        args.path = module.MAIN_OBJ
        if not args.session and not args.system:
            system_bus = module.SYSTEM_BUS

        if hasattr(module, 'IS_OBJECT_MANAGER'):
            args.is_object_manager = module.IS_OBJECT_MANAGER
        else:
            args.is_object_manager = False

        if args.is_object_manager and not hasattr(module, 'MAIN_IFACE'):
            args.interface = dbusmock.mockobject.OBJECT_MANAGER_IFACE
        else:
            args.interface = module.MAIN_IFACE

    main_loop = GLib.MainLoop()
    bus = dbusmock.testcase.DBusTestCase.get_dbus(system_bus)

    # quit mock when the bus is going down
    bus.add_signal_receiver(main_loop.quit, signal_name='Disconnected',
                            path='/org/freedesktop/DBus/Local',
                            dbus_interface='org.freedesktop.DBus.Local')

    bus_name = dbus.service.BusName(args.name,
                                    bus,
                                    allow_replacement=True,
                                    replace_existing=True,
                                    do_not_queue=True)

    main_object = dbusmock.mockobject.DBusMockObject(bus_name, args.path,
                                                     args.interface, {},
                                                     args.logfile,
                                                     args.is_object_manager)

    parameters = None
    if args.parameters:
        try:
            parameters = json.loads(args.parameters)
        except ValueError as detail:
            sys.stderr.write(f'Malformed JSON given for parameters: {detail}\n')
            sys.exit(2)

        if not isinstance(parameters, dict):
            sys.stderr.write('JSON parameters must be a dictionary\n')
            sys.exit(2)

    if args.template:
        main_object.AddTemplate(args.template, parameters)

    dbusmock.mockobject.objects[args.path] = main_object
    main_loop.run()
