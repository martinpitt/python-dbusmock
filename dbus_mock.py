#!/usr/bin/python3
'''Mock D-BUS objects for test suites.'''

import argparse
import time
import sys
import unittest
import subprocess
import signal
import os

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GObject

# global path -> DBusMockObject mapping
objects = {}

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


class DBusMockObject(dbus.service.Object):
    def __init__(self, bus_name, path, interface, props, logfile=None):
        super().__init__(bus_name, path)

        self.bus_name = bus_name
        self.interface = interface
        self.props = props
        # name -> (in_signature, out_signature, code)
        self.methods = {}

        if logfile:
            self.logfile = open(logfile, 'w')
        else:
            self.logfile = None

    def __del__(self):
        if self.logfile:
            print('DBusMockObject __del__ closing log')
            self.logfile.close()

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        try:
            return self.GetAll(interface_name)[property_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownProperty',
                'no such property ' + property_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name, *args, **kwargs):
        if interface_name == self.interface:
            return self.props
        else:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownInterface',
                'no such interface ' + interface_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ssv', out_signature='')
    def Set(self, interface_name, property_name, value, *args, **kwargs):
        if interface_name == self.interface:
            if property_name in self.props:
                self.props[property_name] = value
            else:
                raise dbus.exceptions.DBusException(
                    self.interface + '.UnknownProperty',
                    'no such property ' + property_name)
        else:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownInterface',
                'no such interface ' + interface_name)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='ssa{sv}a(ssss)',
                         out_signature='')
    def AddObject(self, path, main_interface, properties, methods):
        '''Add a new object to the daemon.'''
        
        if path in objects:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Mock.NameError',
                'object %s already exists' % path)

        obj = DBusMockObject(self.bus_name,
                             path,
                             main_interface,
                             properties)
        obj.AddMethods(methods)

        objects[path] = obj

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='s',
                         out_signature='')
    def RemoveObject(self, path):
        '''Remove an object from the daemon.'''

        try:
            del objects[path]
        except KeyError:
            raise dbus.exceptions.DBusException(
                'org.freedesktop.DBus.Mock.NameError',
                'object %s does not exist' % path)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='ssss',
                         out_signature='')
    def AddMethod(self, name, in_sig, out_sig, code):
        '''Add a method to this object'''

        n_args = len(dbus.Signature(in_sig))
        self.methods[name] = (in_sig, out_sig, code)

        # we need to have separate methods for dbus-python, so clone
        # mock_method(); using message_keyword with this dynamic approach fails
        # because inspect cannot handle those, so pass it on as first
        # positional argument
        method = lambda self, *args, **kwargs: DBusMockObject.mock_method(self, name, *args, **kwargs)

        dbus_method = dbus.service.method(self.interface,
                                          out_signature=out_sig)(method)
        setattr(self.__class__, name, dbus_method)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='a(ssss)',
                         out_signature='')
    def AddMethods(self, methods):
        '''Add methods to this object'''

        for method in methods:
            self.AddMethod(*method)

    @dbus.service.method('org.freedesktop.DBus.Mock',
                         in_signature='ssv',
                         out_signature='')
    def AddProperty(self, interface_name, property_name, value):
        if interface_name == self.interface:
            if property_name not in self.props:
                self.props[property_name] = value
            else:
                raise dbus.exceptions.DBusException(
                    self.interface + '.PropertyExists',
                    'property %s already exists' % property_name)
        else:
            raise dbus.exceptions.DBusException(
                self.interface + '.UnknownInterface',
                'no such interface ' + interface_name)

    def mock_method(self, dbus_method, *args, **kwargs):
        #print('mock_method', dbus_method, self, args, kwargs, file=sys.stderr)
        self.log(dbus_method)
        (in_sig, out_sig, code) = self.methods[dbus_method]
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


class DBusTestCase(unittest.TestCase):
    '''Base class for D-BUS mock tests'''

    session_bus_pid = None
    system_bus_pid = None

    @classmethod
    def start_session_bus(klass):
        '''Set up a fake session bus.
        
        This gets stopped in tearDownClass().
        '''
        (klass.session_bus_pid, addr) = klass.start_dbus()
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = addr

    @classmethod
    def start_system_bus(klass):
        '''Set up a fake system bus.
        
        This gets stopped in tearDownClass().
        '''
        (klass.system_bus_pid, addr) = klass.start_dbus()
        os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = addr

    @classmethod
    def tearDownClass(klass):
        '''Stop fake session/system buses.'''

        if klass.session_bus_pid is not None:
            klass.stop_dbus(klass.session_bus_pid)
            del os.environ['DBUS_SESSION_BUS_ADDRESS']
            klass.session_bus_pid = None
        if klass.system_bus_pid is not None:
            klass.stop_dbus(klass.system_bus_pid)
            del os.environ['DBUS_SYSTEM_BUS_ADDRESS']
            klass.system_bus_pid = None

    @classmethod
    def start_dbus(klass):
        '''Start a D-BUS daemon.

        Return (pid, address) pair.
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
        '''Stop a D-BUS daemon'''

        os.kill(pid, signal.SIGTERM)
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass

    @classmethod
    def wait_for_bus_object(klass, dest, path, system_bus=False):
        '''Wait for an object to appear on D-BUS
        
        Raise an exception if object does not appear within 5 seconds.
        '''
        if system_bus:
            bus = dbus.SystemBus(private=True)
        else:
            bus = dbus.SessionBus(private=True)

        timeout = 50
        last_exc = None
        while timeout > 0:
            try:
                p = dbus.Interface(bus.get_object(dest, path),
                                   dbus_interface=dbus.PROPERTIES_IFACE)
                p.GetAll('org.freedesktop.DBus.BogusIface')
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
        '''Run a DBusMockObject instance in a separate process.

        The daemon will terminate automatically when the D-BUS that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns the Popen object of the spawned daemon.
        '''
        argv = [__file__]
        if system_bus:
            argv.append('--system')
        argv.append(name)
        argv.append(path)
        argv.append(interface)

        daemon = subprocess.Popen(argv, stdout=stdout)

        # wait for daemon to start up
        klass.wait_for_bus_object(name, path, system_bus)

        return daemon


if __name__ == '__main__':
    args = parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus_name = dbus.service.BusName(args.name,
                                    args.system and dbus.SystemBus() or dbus.SessionBus(),
                                    allow_replacement=True,
                                    replace_existing=True,
                                    do_not_queue=True)

    main_object = DBusMockObject(bus_name, args.path, args.interface, {}, args.logfile)
    GObject.MainLoop().run()
