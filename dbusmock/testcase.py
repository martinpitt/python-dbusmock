'''unittest.TestCase convenience methods for DBusMocks'''

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

import enum
import errno
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import dbus
import dbus.proxies

from dbusmock.mockobject import MOCK_IFACE, OBJECT_MANAGER_IFACE, load_module


class BusType(enum.Enum):
    '''Represents a system or session bus'''
    SESSION = "session"
    SYSTEM = "system"

    @property
    def environ(self) -> Tuple[str, Optional[str]]:
        '''Returns the name and value of this bus' address environment variable'''
        env = f'DBUS_{self.value.upper()}_BUS_ADDRESS'
        value = os.environ.get(env)
        return env, value

    def get_connection(self) -> dbus.bus.Connection:
        '''Get a dbus.bus.BusConnection() object to this bus.

        This uses the current environment variables for this bus (if any) and falls back
        to dbus.SystemBus() or dbus.SessionBus() otherwise.

        This is preferrable to dbus.SystemBus() and dbus.SessionBus() as those
        do not get along with multiple changing local test buses.
        '''
        _, val = self.environ
        if val:
            return dbus.bus.BusConnection(val)
        if self == BusType.SYSTEM:
            return dbus.SystemBus()
        return dbus.SessionBus()

    def reload_configuration(self):
        '''Notify this bus that it needs to reload the configuration'''
        bus = self.get_connection()
        dbus_obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_if = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')
        dbus_if.ReloadConfig()

    def wait_for_bus_object(self, dest: str, path: str, timeout: float = 60.0):
        '''Wait for an object to appear on D-Bus

        Raise an exception if object does not appear within one minute. You can
        change the timeout in seconds with the "timeout" keyword argument.
        '''
        bus = self.get_connection()

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

            timeout -= 0.1
            time.sleep(0.1)
        if timeout <= 0:
            assert timeout > 0, f'timed out waiting for D-Bus object {path}: {last_exc}'


class PrivateDBus:
    '''A D-Bus daemon instance that represents a private session or system bus.

    If used as a context manager it will automatically start the bus and clean up
    after itself on exit:

        >>> with PrivateDBus(BusType.SESSION) as bus:
        >>>    do_something(bus)

    Otherwise, `start()` and `stop()` manually.
    '''
    def __init__(self, bustype: BusType):
        self.bustype = bustype
        self._daemon: Optional[subprocess.Popen] = None

        self._datadir = Path(tempfile.mkdtemp(prefix='dbusmock_data_'))
        self._socket = self._datadir / f"{self.bustype.value}_bus.socket"
        subdir = "system-services" if bustype == BusType.SYSTEM else "services"
        self._servicedir = self._datadir / subdir
        self._servicedir.mkdir(parents=True)

        self._config = self._servicedir / f'dbusmock_{self.bustype.value}_cfg'
        self._config.write_text(f'''<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
     "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
    <busconfig>
      <type>{self.bustype.value}</type>
      <keep_umask/>
      <listen>unix:path={self._socket}</listen>
      <!-- We do not add standard_{self.bustype.value}_servicedirs (i.e. we only have our private services directory). -->
      <servicedir>{self._servicedir}</servicedir>
      <policy context="default">
        <allow send_destination="*" eavesdrop="true"/>
        <allow eavesdrop="true"/>
        <allow own="*"/>
      </policy>
    </busconfig>
    ''')

    def __enter__(self) -> "PrivateDBus":
        # Allow for start() to be called manually even before the `with`
        if self._daemon is None:
            self.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Allow for stop() to be called manually within `with`
        if self._daemon is not None:
            self.stop()

    @property
    def address(self) -> str:
        '''Returns this D-Bus' address in the environment variable format, i.e. something like
        unix:path=/path/to/socket
        '''
        assert self._daemon is not None, "Call start() first"
        return f"unix:path={self._socket}"

    @property
    def servicedir(self) -> Path:
        '''The services directory (full path) for any ``.service`` files that need to be known to
        this D-Bus.
        '''
        return self._servicedir

    @property
    def pid(self) -> int:
        '''Return the pid of this D-Bus daemon process'''
        assert self._daemon is not None, "Call start() first"
        return self._daemon.pid

    def start(self):
        '''Start the D-Bus daemon'''
        argv = ['dbus-daemon', f'--config-file={self._config}']
        # pylint: disable=consider-using-with
        self._daemon = subprocess.Popen(argv)
        for _ in range(10):
            if self._socket.exists():
                break
            time.sleep(0.1)
        else:
            assert self._socket.exists(), "D-Bus socket never created"

        env, _ = self.bustype.environ
        os.environ[env] = self.address

    def stop(self):
        '''Stop the D-Bus daemon'''
        if self._daemon:
            try:
                self._daemon.terminate()
                try:
                    self._daemon.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self._daemon.kill()
            except ProcessLookupError:
                pass
            self._daemon = None

        shutil.rmtree(self._datadir, ignore_errors=True)

    def enable_service(self, service: str):
        '''Enable the given well-known service name inside dbusmock

        This symlinks a service file from the usual dbus service directories
        into the dbusmock environment. Doing that allows the service to be
        launched automatically if they are defined within $XDG_DATA_DIRS.

        The daemon configuration is reloaded if a test bus is running.
        '''
        xdg_data_dirs = os.environ.get('XDG_DATA_DIRS') or '/usr/local/share/:/usr/share/'
        subdir = "system-services" if self.bustype == BusType.SYSTEM else "services"
        for d in xdg_data_dirs.split(':'):
            src = Path(d) / 'dbus-1' / subdir / f'{service}.service'
            if src.exists():
                assert self._servicedir.exists()
                (self._servicedir / f'{service}.service').symlink_to(src)
                break
        else:
            raise AssertionError(f"Service {service} not found in XDG_DATA_DIRS ({xdg_data_dirs})")

        if self._daemon:
            self.bustype.reload_configuration()

    def disable_service(self, service):
        '''Disable the given well known service name inside dbusmock

        This unlink's the .service file for the service and reloads the
        daemon configuration if a test bus is running.
        '''
        try:
            (self._servicedir / f'{service}.service').unlink()
        except OSError:
            raise AssertionError(f"Service {service} not found") from None

        if self._daemon:
            self.bustype.reload_configuration()


class DBusTestCase(unittest.TestCase):
    '''Base class for D-Bus mock tests.

    This provides some convenience API to start/stop local D-Buses, so that you
    can run a private local session and/or system bus to run mocks on.

    This also provides a spawn_server() static method to run the D-Bus mock
    server in a separate process.
    '''
    session_bus_pid = None
    system_bus_pid = None
    _DBusTestCase__datadir = None
    _busses: Dict[BusType, PrivateDBus] = {
          BusType.SESSION: None,  # type: ignore[dict-item]
          BusType.SYSTEM: None,  # type: ignore[dict-item]
    }

    @staticmethod
    def _bus(bustype: BusType) -> PrivateDBus:
        '''Return (and create if necessary) the singleton DBus for the given bus type'''
        if not DBusTestCase._busses.get(bustype):
            DBusTestCase._busses[bustype] = PrivateDBus(bustype)
        return DBusTestCase._busses[bustype]

    @staticmethod
    def get_services_dir(system_bus: bool = False) -> str:
        '''Returns the private services directory for the bus type in question.
        This allows dropping in a .service file so that the dbus server inside
        dbusmock can launch it.
        '''
        bus = DBusTestCase._bus(bustype=BusType.SYSTEM if system_bus else BusType.SESSION)
        return str(bus.servicedir)

    @classmethod
    def tearDownClass(cls):
        for bustype in BusType:
            bus = DBusTestCase._busses.get(bustype)
            if bus:
                bus.stop()
                setattr(DBusTestCase, f'{bustype.value}_bus_pid', None)
                del DBusTestCase._busses[bustype]

    @classmethod
    def __start_bus(cls, bus_type) -> None:
        bustype = BusType(bus_type)
        old_pid = getattr(DBusTestCase, f"{bustype.value}_bus_pid")
        assert old_pid is None, f"PID {old_pid} still alive?"
        assert DBusTestCase._busses.get(bustype) is None
        bus = DBusTestCase._bus(bustype)
        bus.start()
        setattr(DBusTestCase, f'{bustype.value}_bus_pid', bus.pid)

    @classmethod
    def start_session_bus(cls) -> None:
        '''Set up a private local session bus

        This gets stopped automatically at class teardown.
        '''
        cls.__start_bus('session')

    @classmethod
    def start_system_bus(cls) -> None:
        '''Set up a private local system bus

        This gets stopped automatically at class teardown.
        '''
        cls.__start_bus('system')

    @staticmethod
    def start_dbus(conf: Optional[str] = None) -> Tuple[int, str]:
        '''Start a D-Bus daemon

        Return (pid, address) pair.

        Normally you do not need to call this directly. Use start_system_bus()
        and start_session_bus() instead.
        '''
        argv = ['dbus-daemon', '--fork', '--print-address=1', '--print-pid=1']
        if conf:
            argv.append('--config-file=' + str(conf))
        else:
            argv.append('--session')
        lines = subprocess.check_output(argv, universal_newlines=True).strip().splitlines()
        assert len(lines) == 2, 'expected exactly 2 lines of output from dbus-daemon'
        # usually the first line is the address, but be lenient and accept any order
        try:
            return (int(lines[1]), lines[0])
        except ValueError:
            return (int(lines[0]), lines[1])

    @staticmethod
    def stop_dbus(pid: int) -> None:
        '''Stop a D-Bus daemon

        Normally you do not need to call this directly. When you use
        start_system_bus() and start_session_bus(), these buses are
        automatically stopped in tearDownClass().
        '''
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        for _ in range(50):
            try:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break
            except OSError as e:
                if e.errno == errno.ESRCH:
                    break
                raise
            time.sleep(0.1)
        else:
            sys.stderr.write('ERROR: timed out waiting for bus process to terminate\n')
            os.kill(pid, signal.SIGKILL)
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    @staticmethod
    def get_dbus(system_bus: bool = False) -> dbus.Bus:
        '''Get a dbus.bus.BusConnection() object to this bus

        This is preferrable to dbus.SystemBus() and dbus.SessionBus() as those
        do not get along with multiple changing local test buses.

        This is a legacy method kept for backwards compatibility, use
        BusType.get_connection() instead.
        '''
        bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        return bustype.get_connection()

    @staticmethod
    def wait_for_bus_object(dest: str, path: str, system_bus: bool = False, timeout: int = 600):
        '''Wait for an object to appear on D-Bus

        Raise an exception if object does not appear within one minute. You can
        change the timeout with the "timeout" keyword argument which specifies
        deciseconds.

        This is a legacy method kept for backwards compatibility, use
        BusType.wait_for_bus_object() instead.
        '''
        bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        bustype.wait_for_bus_object(dest, path, timeout / 10.0)

    @staticmethod
    def spawn_server(name: str, path: str, interface: str, system_bus: bool = False, stdout=None) -> subprocess.Popen:
        '''Run a DBusMockObject instance in a separate process

        The daemon will terminate automatically when the D-Bus that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns the Popen object of the spawned daemon.

        This is a legacy method kept for backwards compatibility,
        use SpawnedMock.spawn_for_name() instead.
        '''
        bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        server = SpawnedMock.spawn_for_name(name, path, interface, bustype, stdout=stdout, stderr=None)
        return server.process

    @staticmethod
    def spawn_server_template(template: str,
                              parameters: Optional[Dict[str, Any]] = None,
                              stdout=None,
                              system_bus: Optional[bool] = None) -> Tuple[subprocess.Popen, dbus.proxies.ProxyObject]:
        '''Run a D-Bus mock template instance in a separate process

        This starts a D-Bus mock process and loads the given template with
        (optional) parameters into it. For details about templates see
        dbusmock.DBusMockObject.AddTemplate().

        Usually a template should specify SYSTEM_BUS = False/True to select whether it
        gets loaded on the session or system bus. This can be overridden with the system_bus
        parameter. For templates which don't set SYSTEM_BUS, this parameter has to be set.

        The daemon will terminate automatically when the D-Bus that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns a pair (daemon Popen object, main dbus object).

        This is a legacy method kept for backwards compatibility,
        use SpawnedMock.spawn_with_template() instead.
        '''
        if system_bus is not None:  # noqa: SIM108
            bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        else:
            bustype = None
        server = SpawnedMock.spawn_with_template(template, parameters, bustype, stdout, stderr=None)
        return server.process, server.obj

    @staticmethod
    def enable_service(service, system_bus: bool = False) -> None:
        '''Enable the given well known service name inside dbusmock

        This symlinks a service file from the usual dbus service directories
        into the dbusmock environment. Doing that allows the service to be
        launched automatically if they are defined within $XDG_DATA_DIRS.

        The daemon configuration is reloaded if a test bus is running.

        This is a legacy method kept for backwards compatibility. Use
        PrivateDBus.enable_service() instead.
        '''
        bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        bus = DBusTestCase._bus(bustype)
        bus.enable_service(service)

    @staticmethod
    def disable_service(service, system_bus: bool = False) -> None:
        '''Disable the given well known service name inside dbusmock

        This unlink's the .service file for the service and reloads the
        daemon configuration if a test bus is running.
        '''
        bustype = BusType.SYSTEM if system_bus else BusType.SESSION
        bus = DBusTestCase._bus(bustype)
        bus.disable_service(service)


class SpawnedMock:
    '''
    An instance of a D-Bus mock template instance in a separate process.

    See SpawnedMock.spawn_for_name() and SpawnedMock.spawn_with_template()
    the typical entry points.
    '''
    def __init__(self, process: subprocess.Popen, obj: dbus.proxies.ProxyObject):
        self._process = process
        self._process_is_running = True
        self._obj = obj

    @property
    def process(self) -> subprocess.Popen:
        '''Returns the process that is this mock template'''
        return self._process

    @property
    def obj(self):
        '''The D-Bus object this server was spawned for'''
        return self._obj

    def __enter__(self) -> "SpawnedMock":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.terminate()

    def terminate(self):
        '''Terminate the process'''
        if self._process.returncode is None:
            self._process.poll()

        if self._process.returncode is None:
            if self._process.stdout:
                self._process.stdout.close()
            if self._process.stderr:
                self._process.stderr.close()
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except ProcessLookupError:
                pass

    @property
    def stdout(self):
        '''
        The stdout of the process, if no caller-specific stdout
        was specified in spawn_for_name() or spawn_with_template().
        '''
        return self._process.stdout

    @property
    def stderr(self):
        '''
        The stderr of the process, if no caller-specific stderr
        was specified in spawn_for_name() or spawn_with_template().
        '''
        return self._process.stderr

    @classmethod
    def spawn_for_name(cls, name: str, path: str, interface: str,
                       bustype: BusType = BusType.SESSION,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE) -> "SpawnedMock":
        '''Run a DBusMockObject instance in a separate process

        The daemon will terminate automatically when the D-Bus that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        By default, stdout and stderr of the spawned process is available via the
        SpawnedMock.stdout and SpawnedMock.stderr properties on the returned object.
        '''
        argv = [sys.executable, '-m', 'dbusmock', f'--{bustype.value}', name, path, interface]
        bus = bustype.get_connection()
        if bus.name_has_owner(name):
            raise AssertionError(f'Trying to spawn a server for name {name} but it is already owned!')

        # pylint: disable=consider-using-with
        daemon = subprocess.Popen(argv, stdout=stdout, stderr=stderr)

        # wait for daemon to start up
        bustype.wait_for_bus_object(name, path)
        obj = bus.get_object(name, path)

        return cls(
            process=daemon,
            obj=obj
        )

    @classmethod
    def spawn_with_template(cls,
                            template: str,
                            parameters: Optional[Dict[str, Any]] = None,
                            bustype: Optional[BusType] = None,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE):
        '''Run a D-Bus mock template instance in a separate process

        This starts a D-Bus mock process and loads the given template with
        (optional) parameters into it. For details about templates see
        dbusmock.DBusMockObject.AddTemplate().

        Usually a template should specify SYSTEM_BUS = False/True to select whether it
        gets loaded on the session or system bus. This can be overridden with the system_bus
        parameter. For templates which don't set SYSTEM_BUS, this parameter has to be set.

        The daemon will terminate automatically when the D-Bus that it connects
        to goes down.  If that does not happen (e. g. you test on the actual
        system/session bus), you need to kill it manually.

        This function blocks until the spawned DBusMockObject is ready and
        listening on the bus.

        Returns a pair (daemon Popen object, main dbus object).
        '''

        # we need the bus address from the template module
        module = load_module(template)

        is_object_manager = module.IS_OBJECT_MANAGER if hasattr(module, 'IS_OBJECT_MANAGER') else False

        if is_object_manager and not hasattr(module, 'MAIN_IFACE'):  # noqa: SIM108
            interface_name = OBJECT_MANAGER_IFACE
        else:
            interface_name = module.MAIN_IFACE

        if bustype is None:
            bustype = BusType.SYSTEM if module.SYSTEM_BUS else BusType.SESSION

        assert bustype is not None

        server = SpawnedMock.spawn_for_name(module.BUS_NAME, module.MAIN_OBJ, interface_name, bustype, stdout, stderr)
        if not parameters:
            parameters = dbus.Dictionary({}, signature='sv')
        server.obj.AddTemplate(template, parameters, dbus_interface=MOCK_IFACE)
        return server
