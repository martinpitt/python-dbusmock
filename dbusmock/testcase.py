# coding: UTF-8
'''unittest.TestCase convenience methods for DBusMocks'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2012 Canonical Ltd.'
__license__ = 'LGPL 3+'

import time
import sys
import unittest
import subprocess
import signal
import os
import errno
import tempfile

import dbus

from dbusmock.mockobject import MOCK_IFACE, OBJECT_MANAGER_IFACE, load_module


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
        # create a temporary configuration which makes the fake bus actually
        # appear a type "system"
        with tempfile.NamedTemporaryFile(prefix='dbusmock_cfg') as c:
            c.write(b'''<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>system</type>
  <keep_umask/>
  <listen>unix:tmpdir=/tmp</listen>
  <standard_system_servicedirs />

  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
''')
            c.flush()
            (DBusTestCase.system_bus_pid, addr) = klass.start_dbus(conf=c.name)
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
    def start_dbus(klass, conf=None):
        '''Start a D-BUS daemon

        Return (pid, address) pair.

        Normally you do not need to call this directly. Use start_system_bus()
        and start_session_bus() instead.
        '''
        argv = ['dbus-launch']
        if conf:
            argv.append('--config-file=' + conf)
        out = subprocess.check_output(argv, universal_newlines=True)
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
    def wait_for_bus_object(klass, dest, path, system_bus=False, timeout=50):
        '''Wait for an object to appear on D-BUS

        Raise an exception if object does not appear within 5 seconds. You can
        change the timeout with the "timeout" keyword argument which specifies
        deciseconds.
        '''
        bus = klass.get_dbus(system_bus)

        last_exc = None
        # we check whether the name is owned first, to avoid race conditions
        # with service activation; once it's owned, wait until we can actually
        # call methods
        while timeout > 0:
            if bus.name_has_owner(dest):
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
        argv = [sys.executable, '-m', 'dbusmock']
        if system_bus:
            argv.append('--system')
        argv.append(name)
        argv.append(path)
        argv.append(interface)

        daemon = subprocess.Popen(argv, stdout=stdout)

        # wait for daemon to start up
        klass.wait_for_bus_object(name, path, system_bus)

        return daemon

    @classmethod
    def spawn_server_template(klass, template, parameters=None, stdout=None):
        '''Run a D-BUS mock template instance in a separate process

        This starts a D-BUS mock process and loads the given template with
        (optional) parameters into it. For details about templates see
        dbusmock.DBusMockObject.AddTemplate().

        The daemon will terminate automatically when the D-BUS that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns a pair (daemon Popen object, main dbus object).
        '''
        # we need the bus address from the template module
        module = load_module(template)

        if hasattr(module, 'IS_OBJECT_MANAGER'):
            is_object_manager = module.IS_OBJECT_MANAGER
        else:
            is_object_manager = False

        if is_object_manager and not hasattr(module, 'MAIN_IFACE'):
            interface_name = OBJECT_MANAGER_IFACE
        else:
            interface_name = module.MAIN_IFACE

        daemon = klass.spawn_server(module.BUS_NAME, module.MAIN_OBJ,
                                    interface_name, module.SYSTEM_BUS, stdout)

        bus = klass.get_dbus(module.SYSTEM_BUS)
        obj = bus.get_object(module.BUS_NAME, module.MAIN_OBJ)
        if not parameters:
            parameters = dbus.Dictionary({}, signature='sv')
        obj.AddTemplate(template, parameters,
                        dbus_interface=MOCK_IFACE)

        return (daemon, obj)

# Python 2 backwards compatibility
if sys.version_info[0] < 3:
    import re

    def assertRegex(self, value, pattern):
        if not re.search(pattern, value):
            raise self.failureException('%r not found in %s' % (pattern, value))
    DBusTestCase.assertRegex = assertRegex
