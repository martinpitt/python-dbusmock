#!/usr/bin/python3
# coding: UTF-8
'''Mock D-BUS objects for test suites.'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__  = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import argparse
import time
import sys
import unittest
import subprocess
import signal
import os
import errno

import dbus
import dbus.service

# global path -> DBusMockObject mapping
objects = {}


class DBusMockObject(dbus.service.Object):
    '''Mock D-Bus object

    This can be configured to have arbitrary methods (including code execution)
    and properties via methods on the org.freedesktop.DBus.Mock interface, so
    that you can control the mock from any programming language.
    '''

    def __init__(self, bus_name, path, interface, props, logfile=None):
        '''Create a new DBusMockObject

        bus_name: A dbus.service.BusName instance where the object will be put on
        path: D-Bus object path
        interface: Primary D-Bus interface name of this object (where
                   properties and methods will be put on)
        props: A property_name (string) → property (Variant) map with initial
               properties on "interface"
        logfile: When given, method calls will be logged into that file name;
                 if None, logging will be written to stdout.
        '''
        super(self.__class__, self).__init__(bus_name, path)

        self.bus_name = bus_name
        self.interface = interface
        # interface -> name -> value
        self.props = {}
        self.props[interface] = props

        # interface -> name -> (in_signature, out_signature, code, dbus_wrapper_fn)
        self.methods = {interface: {}}

        if logfile:
            self.logfile = open(logfile, 'w')
        else:
            self.logfile = None

    def __del__(self):
        if self.logfile:
            self.logfile.close()

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        '''Standard D-Bus API for getting a property value'''

        try:
            return self.GetAll(interface_name)[property_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownProperty',
                'no such property ' + property_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name, *args, **kwargs):
        '''Standard D-Bus API for getting all property values'''

        try:
            return self.props[interface_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownInterface',
                'no such interface ' + interface_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ssv', out_signature='')
    def Set(self, interface_name, property_name, value, *args, **kwargs):
        '''Standard D-Bus API for setting a property value'''

        try:
            iface_props = self.props[interface_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownInterface',
                'no such interface ' + interface_name)

        if property_name not in iface_props:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownProperty',
                'no such property ' + property_name)

        iface_props[property_name] = value

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='ssa{sv}a(ssss)',
                         out_signature='')
    def AddObject(self, path, interface, properties, methods):
        '''Add a new D-Bus object to the mock
        
        path: D-Bus object path
        interface: Primary D-Bus interface name of this object (where
                   properties and methods will be put on)
        properties: A property_name (string) → value map with initial
                    properties on "interface"
        methods: An array of 4-tuples (name, in_sig, out_sig, code) describing
                 methods to add to "interface"; see AddMethod() for details of
                 the tuple values

        Example:
        dbus_proxy.AddObject('/com/example/Foo/Manager',
                             'com.example.Foo.Control',
                             {
                                 'state': dbus.String('online', variant_level=1),
                             },
                             [
                                 ('Start', '', '', ''),
                                 ('EchoInt', 'i', 'i', 'ret = args[0]'),
                                 ('GetClients', '', 'ao', 'ret = ["/com/example/Foo/Client1"]'),
                             ])
        '''
        if path in objects:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Mock.NameError',
                'object %s already exists' % path)

        obj = DBusMockObject(self.bus_name,
                             path,
                             interface,
                             properties)
        obj.AddMethods(interface, methods)

        objects[path] = obj

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='s',
                         out_signature='')
    def RemoveObject(self, path):
        '''Remove a D-Bus object from the mock'''

        try:
            del objects[path]
        except KeyError:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Mock.NameError',
                'object %s does not exist' % path)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='sssss',
                         out_signature='')
    def AddMethod(self, interface, name, in_sig, out_sig, code):
        '''Add a method to this object
        
        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the method to the object's main
                   interface (as specified on construction).
        name: Name of the method
        in_sig: Signature of input arguments; for example "ias" for a method
                that takes an int32 and a string array as arguments; see
                http://dbus.freedesktop.org/doc/dbus-specification.html#message-protocol-signatures
        out_sig: Signature of output arguments; for example "s" for a method
                 that returns a string; use '' for methods that do not return
                 anything.
        code: Python 3 code to run in the method call; you have access to the
              arguments through the "args" list, and can set the return value
              by assigning a value to the "ret" variable. You can also read the
              global "objects" variable, which is a dictionary mapping object
              paths to DBusMockObject instances.
              
              When specifying '', the method will not do anything (except
              logging) and return None.
        '''
        if not interface:
            interface = self.interface
        n_args = len(dbus.Signature(in_sig))

        # we need to have separate methods for dbus-python, so clone
        # mock_method(); using message_keyword with this dynamic approach fails
        # because inspect cannot handle those, so pass on interface and method
        # name as first positional arguments
        method = lambda self, *args, **kwargs: DBusMockObject.mock_method(
            self, interface, name, in_sig, *args, **kwargs)

        # we cannot specify in_signature here, as that trips over a consistency
        # check in dbus-python; we need to set it manually instead
        dbus_method = dbus.service.method(interface,
                                          out_signature=out_sig)(method)
        dbus_method.__name__ = str(name)
        dbus_method._dbus_in_signature = in_sig
        dbus_method._dbus_args = ['arg%i' % i for i in range(1, n_args + 1)]

        setattr(self.__class__, name, dbus_method)

        self.methods.setdefault(interface, {})[str(name)] = (in_sig, out_sig, code, dbus_method)


    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='sa(ssss)',
                         out_signature='')
    def AddMethods(self, interface, methods):
        '''Add several methods to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the method to the object's main
                   interface (as specified on construction).
        methods: list of 4-tuples (name, in_sig, out_sig, code) describing one
                 method each. See AddMethod() for details of the tuple values.
        '''
        for method in methods:
            self.AddMethod(interface, *method)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='ssv',
                         out_signature='')
    def AddProperty(self, interface, name, value):
        '''Add property to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the property to the object's main
                   interface (as specified on construction).
        name: Property name.
        value: Property value.
        '''
        if not interface:
            interface = self.interface
        try:
            self.props[interface][name]
            raise dbus.exceptions.DBusException(
                self.interface + '.PropertyExists',
                'property %s already exists' % name)
        except KeyError:
            # this is what we expect
            pass
        self.props.setdefault(interface, {})[name] = value

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='sa{sv}',
                         out_signature='')
    def AddProperties(self, interface, properties):
        '''Add several properties to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the property to the object's main
                   interface (as specified on construction).
        properties: A property_name (string) → value map
        '''
        for k, v in properties.items():
            self.AddProperty(interface, k, v)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='sssav',
                         out_signature='')
    def EmitSignal(self, interface, name, signature, args):
        '''Emit a signal from the object.

        interface: D-Bus interface to send the signal from. For convenience you
                   can specify '' here to add the method to the object's main
                   interface (as specified on construction).
        name: Name of the signal
        signature: Signature of input arguments; for example "ias" for a signal
                that takes an int32 and a string array as arguments; see
                http://dbus.freedesktop.org/doc/dbus-specification.html#message-protocol-signatures
        args: variant array with signal arguments; must match order and type in
              "signature"
        '''
        if not interface:
            interface = self.interface

        # convert types of arguments according to signature, using
        # MethodCallMessage.append(); this will also provide type/length
        # checks, except for the case of an empty signature
        if signature == '' and len(args) > 0:
            raise TypeError('Fewer items found in D-Bus signature than in Python arguments')
        m = dbus.connection.MethodCallMessage('a.b', '/a', 'a.b', 'a')
        m.append(signature=signature, *args)
        args = m.get_args_list()

        fn = lambda self, *args: self.log('emit %s.%s: %s' % (interface, name, args))
        fn.__name__ = str(name)
        dbus_fn = dbus.service.signal(interface)(fn)
        dbus_fn._dbus_signature = signature
        dbus_fn._dbus_args = ['arg%i' % i for i in range(1, len(args) + 1)]

        dbus_fn(self, *args)

    def mock_method(self, interface, dbus_method, in_signature, *args, **kwargs):
        '''Master mock method.

        This gets "instantiated" in AddMethod(). Execute the code snippet of
        the method and return the "ret" variable if it was set.
        '''
        #print('mock_method', dbus_method, self, in_signature, args, kwargs, file=sys.stderr)

        # convert types of arguments according to signature, using
        # MethodCallMessage.append(); this will also provide type/length
        # checks, except for the case of an empty signature
        if in_signature == '' and len(args) > 0:
            raise TypeError('Fewer items found in D-Bus signature than in Python arguments')
        m = dbus.connection.MethodCallMessage('a.b', '/a', 'a.b', 'a')
        m.append(signature=in_signature, *args)
        args = m.get_args_list()

        self.log(dbus_method)
        code = self.methods[interface][dbus_method][2]
        if code:
            loc = locals().copy()
            exec(code, globals(), loc)
            if 'ret' in loc:
                return loc['ret']

    def log(self, msg):
        '''Log a message, prefixed with a timestamp.

        If a log file was specified in the constructor, it is written there,
        otherwise it goes to stdout.
        '''
        if self.logfile:
            fd = self.logfile
        else:
            fd = sys.stdout

        fd.write('%.3f %s\n' % (time.time(), msg))
        fd.flush()

    @dbus.service.method(dbus.INTROSPECTABLE_IFACE,
                         in_signature='',
                         out_signature='s',
                         path_keyword='object_path',
                         connection_keyword='connection')
    def Introspect(self, object_path, connection):
        '''Return XML description of this object's interfaces, methods and signals.

        This wraps dbus-python's Introspect() method to include the dynamic
        methods and properties.
        '''
        # temporarily add our dynamic methods
        cls = self.__class__.__module__ + '.' + self.__class__.__name__
        orig_interfaces = self._dbus_class_table[cls]

        mock_interfaces = orig_interfaces.copy()
        for interface, methods in self.methods.items():
            for method in methods:
                mock_interfaces.setdefault(interface, {})[method] = self.methods[interface][method][3]
        self._dbus_class_table[cls] = mock_interfaces

        xml = super(self.__class__, self).Introspect(object_path, connection)

        # restore original class table
        self._dbus_class_table[cls] = orig_interfaces

        return xml


class DBusTestCase(unittest.TestCase):
    '''Base class for D-BUS mock tests.
    
    This provides some convenience API to start/stop local D-Buses, so that you
    can run a private local session and/or system bus to run mocks on.

    This also provides a spawn_server() static method to run the D-Bus mock
    server in a separate process.
    '''
    session_bus_pid = None
    system_bus_pid = None

    @classmethod
    def start_session_bus(klass):
        '''Set up a private local session bus
        
        This gets stopped automatically in tearDownClass().
        '''
        (DBusTestCase.session_bus_pid, addr) = klass.start_dbus()
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = addr

    @classmethod
    def start_system_bus(klass):
        '''Set up a private local system bus
        
        This gets stopped automatically in tearDownClass().
        '''
        (DBusTestCase.system_bus_pid, addr) = klass.start_dbus()
        os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = addr

    @classmethod
    def tearDownClass(klass):
        '''Stop private session/system buses'''

        if DBusTestCase.session_bus_pid is not None:
            klass.stop_dbus(DBusTestCase.session_bus_pid)
            del os.environ['DBUS_SESSION_BUS_ADDRESS']
            DBusTestCase.session_bus_pid = None
        if DBusTestCase.system_bus_pid is not None:
            klass.stop_dbus(DBusTestCase.system_bus_pid)
            del os.environ['DBUS_SYSTEM_BUS_ADDRESS']
            DBusTestCase.system_bus_pid = None

    @classmethod
    def start_dbus(klass):
        '''Start a D-BUS daemon

        Return (pid, address) pair.

        Normally you do not need to call this directly. Use start_system_bus()
        and start_session_bus() instead.
        '''
        out = subprocess.check_output(['dbus-launch'], universal_newlines=True)
        variables = {}
        for line in out.splitlines():
            (k, v) = line.split('=', 1)
            variables[k] = v
        return (int(variables['DBUS_SESSION_BUS_PID']),
                variables['DBUS_SESSION_BUS_ADDRESS'])

    @classmethod
    def stop_dbus(klass, pid):
        '''Stop a D-BUS daemon

        Normally you do not need to call this directly. When you use
        start_system_bus() and start_session_bus(), these buses are
        automatically stopped in tearDownClass().
        '''
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        timeout = 50
        while timeout > 0:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as e:
                if e.errno == errno.ESRCH:
                    break
                else:
                    raise
            time.sleep(0.1)
        else:
            sys.stderr.write('ERROR: timed out waiting for bus process to terminate\n')
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    @classmethod
    def get_dbus(klass, system_bus=False):
        '''Get dbus.bus.BusConnection() object

        This is preferrable to dbus.SystemBus() and dbus.SessionBus() as those
        do not get along with multiple changing local test buses.
        '''
        if system_bus:
            if os.environ.get('DBUS_SYSTEM_BUS_ADDRESS'):
                return dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS'])
            else:
                return dbus.SystemBus()
        else:
            if os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
                return dbus.bus.BusConnection(os.environ['DBUS_SESSION_BUS_ADDRESS'])
            else:
                return dbus.SessionBus()

    @classmethod
    def wait_for_bus_object(klass, dest, path, system_bus=False):
        '''Wait for an object to appear on D-BUS
        
        Raise an exception if object does not appear within 5 seconds.
        '''
        bus = klass.get_dbus(system_bus)

        timeout = 50
        last_exc = None
        while timeout > 0:
            try:
                p = dbus.Interface(bus.get_object(dest, path),
                                   dbus_interface=dbus.INTROSPECTABLE_IFACE)
                p.Introspect()
                break
            except dbus.exceptions.DBusException as e:
                last_exc = e
                if '.UnknownInterface' in str(e):
                    break
                pass

            timeout -= 1
            time.sleep(0.1)
        if timeout <= 0:
            assert timeout > 0, 'timed out waiting for D-BUS object %s: %s' % (path, last_exc)

    @classmethod
    def spawn_server(klass, name, path, interface, system_bus=False, stdout=None):
        '''Run a DBusMockObject instance in a separate process

        The daemon will terminate automatically when the D-BUS that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns the Popen object of the spawned daemon.
        '''
        argv = [sys.executable, __file__]
        if system_bus:
            argv.append('--system')
        argv.append(name)
        argv.append(path)
        argv.append(interface)

        daemon = subprocess.Popen(argv, stdout=stdout)

        # wait for daemon to start up
        klass.wait_for_bus_object(name, path, system_bus)

        return daemon

# Python 2 backwards compatibility
if sys.version_info[0] < 3:
    import re
    def assertRegex(self, value, pattern):
        if not re.search(pattern, value):
            raise self.failureException('%r not found in %s' % (pattern, value))
    DBusTestCase.assertRegex = assertRegex


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
                                    DBusTestCase.get_dbus(args.system),
                                    allow_replacement=True,
                                    replace_existing=True,
                                    do_not_queue=True)

    main_object = DBusMockObject(bus_name, args.path, args.interface, {}, args.logfile)
    objects[args.path] = main_object
    GObject.MainLoop().run()
