# coding: UTF-8
'''Mock D-Bus objects for test suites.'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__copyright__ = '(c) 2012 Canonical Ltd.'

import copy
import functools
import importlib
import importlib.util
import os
import sys
import time
import types
from typing import Optional, Dict, Any, List, Tuple, Sequence, KeysView
from xml.etree import ElementTree

import dbus
import dbus.service

# we do not use this ourselves, but mock methods often want to use this
os  # pyflakes pylint: disable=pointless-statement

# global path -> DBusMockObject mapping
objects: Dict[str, 'DBusMockObject'] = {}

MOCK_IFACE = 'org.freedesktop.DBus.Mock'
OBJECT_MANAGER_IFACE = 'org.freedesktop.DBus.ObjectManager'


PropsType = Dict[str, Any]
# (in_signature, out_signature, code, dbus_wrapper_fn)
MethodType = Tuple[str, str, str, str]
# (timestamp, method_name, call_args)
CallLogType = Tuple[int, str, Sequence[Any]]


def load_module(name: str):
    '''Load a mock template Python module from dbusmock/templates/'''

    if os.path.exists(name) and os.path.splitext(name)[1] == '.py':
        spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(name))[0], name)
        assert spec
        mod = importlib.util.module_from_spec(spec)
        with open(name, encoding="UTF-8") as f:
            exec(f.read(), mod.__dict__, mod.__dict__)  # pylint: disable=exec-used
        return mod

    return importlib.import_module('dbusmock.templates.' + name)


def _format_args(args):
    '''Format a D-Bus argument tuple into an appropriate logging string'''

    def format_arg(a):
        if isinstance(a, dbus.Boolean):
            return str(bool(a))
        if isinstance(a, (dbus.Byte, int)):
            return str(int(a))
        if isinstance(a, str):
            return '"' + str(a) + '"'
        if isinstance(a, list):
            return '[' + ', '.join([format_arg(x) for x in a]) + ']'
        if isinstance(a, dict):
            fmta = '{'
            first = True
            for k, v in a.items():
                if first:
                    first = False
                else:
                    fmta += ', '
                fmta += format_arg(k) + ': ' + format_arg(v)
            return fmta + '}'

        # fallback
        return repr(a)

    s = ''
    for a in args:
        if s:
            s += ' '
        s += format_arg(a)
    if s:
        s = ' ' + s
    return s


def _wrap_in_dbus_variant(value):
    dbus_types = [
        dbus.types.ByteArray,
        dbus.types.Int16,
        dbus.types.ObjectPath,
        dbus.types.Struct,
        dbus.types.UInt64,
        dbus.types.Boolean,
        dbus.types.Dictionary,
        dbus.types.Int32,
        dbus.types.Signature,
        dbus.types.UInt16,
        dbus.types.UnixFd,
        dbus.types.Byte,
        dbus.types.Double,
        dbus.types.Int64,
        dbus.types.String,
        dbus.types.UInt32,
    ]
    if isinstance(value, dbus.String):
        return dbus.String(str(value), variant_level=1)
    if isinstance(value, dbus.types.Array):
        return value
    if type(value) in dbus_types:
        return type(value)(value.conjugate(), variant_level=1)
    if isinstance(value, str):
        return dbus.String(value, variant_level=1)
    raise dbus.exceptions.DBusException(f'could not wrap type {type(value)}')


def _convert_args(signature: str, args: Tuple[Any, ...]) -> List[Any]:
    """
    Convert types of arguments according to signature, using
    MethodCallMessage.append(); this will also provide type/length
    checks, except for the case of an empty signature
    """
    try:
        if signature == '' and len(args) > 0:
            raise TypeError('Fewer items found in D-Bus signature than in Python arguments')
        m = dbus.connection.MethodCallMessage('a.b', '/a', 'a.b', 'a')
        m.append(signature=signature, *args)
        return m.get_args_list()
    except Exception as e:
        raise dbus.exceptions.DBusException(f'Invalid arguments: {str(e)}',
                                            name='org.freedesktop.DBus.Error.InvalidArgs')


def loggedmethod(self, func):
    """Decorator for a method to end in the call log"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        fname = func.__name__
        self_arg, args = args[0], args[1:]

        in_signature = getattr(func, '_dbus_in_signature', '')
        args = _convert_args(in_signature, args)

        self.log(fname + _format_args(args))
        self.call_log.append((int(time.time()), fname, args))
        self.MethodCalled(fname, args)

        return func(*[self_arg, *args], **kwargs)

    return wrapper


class DBusMockObject(dbus.service.Object):  # pylint: disable=too-many-instance-attributes
    '''Mock D-Bus object

    This can be configured to have arbitrary methods (including code execution)
    and properties via methods on the org.freedesktop.DBus.Mock interface, so
    that you can control the mock from any programming language.

    Beyond that "remote control" API, this is a standard dbus-python service object, see
    <https://dbus.freedesktop.org/doc/dbus-python/tutorial.html#exporting-objects>.
    '''

    def __init__(self, bus_name: str, path: str, interface: str, props: PropsType,
                 logfile: Optional[str] = None, is_object_manager: bool = False) -> None:
        '''Create a new DBusMockObject

        bus_name: A dbus.service.BusName instance where the object will be put on
        path: D-Bus object path
        interface: Primary D-Bus interface name of this object (where
                   properties and methods will be put on)
        props: A property_name (string) → property (Variant) map with initial
               properties on "interface"
        logfile: When given, method calls will be logged into that file name;
                 if None, logging will be written to stdout. Note that you can
                 also query the called methods over D-Bus with GetCalls() and
                 GetMethodCalls().
        is_object_manager: If True, the GetManagedObjects method will
                           automatically be implemented on the object, returning
                           all objects which have this one’s path as a prefix of
                           theirs. Note that the InterfacesAdded and
                           InterfacesRemoved signals will not be automatically
                           emitted.
        '''
        dbus.service.Object.__init__(self, bus_name, path)

        self.bus_name = bus_name
        self.path = path
        self.interface = interface
        self.is_object_manager = is_object_manager
        self.object_manager: Optional[DBusMockObject] = None

        self._template: Optional[str] = None
        self._template_parameters: Optional[PropsType] = None

        # pylint: disable=consider-using-with
        self.logfile = open(logfile, 'wb') if logfile else None
        self.is_logfile_owner = True
        self.call_log: List[CallLogType] = []

        if props is None:
            props = {}

        self._reset(props)

    def __del__(self) -> None:
        try:
            if self.logfile and self.is_logfile_owner:
                self.logfile.close()
        except AttributeError:
            pass

    def _set_up_object_manager(self) -> None:
        '''Set up this mock object as a D-Bus ObjectManager.'''
        if self.path == '/':
            cond = 'k != \'/\''
        else:
            cond = f'k.startswith(\'{self.path}/\')'

        self.AddMethod(OBJECT_MANAGER_IFACE,
                       'GetManagedObjects', '', 'a{oa{sa{sv}}}',
                       'ret = {dbus.ObjectPath(k): objects[k].props ' +
                       '  for k in objects.keys() if ' + cond + '}')
        self.object_manager = self

    def _reset(self, props: PropsType) -> None:
        # interface -> name -> value
        self.props = {self.interface: props}

        # interface -> name -> (in_signature, out_signature, code, dbus_wrapper_fn)
        self.methods: Dict[str, Dict[str, MethodType]] = {self.interface: {}}

        if self.is_object_manager:
            self._set_up_object_manager()

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name: str, property_name: str) -> Any:
        '''Standard D-Bus API for getting a property value'''

        self.log(f'Get {self.path} {interface_name}.{property_name}')

        if not interface_name:
            interface_name = self.interface
        try:
            return self.GetAll(interface_name)[property_name]
        except KeyError as e:
            raise dbus.exceptions.DBusException(
                'no such property ' + property_name,
                name=self.interface + '.UnknownProperty') from e

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name: str, *_, **__) -> PropsType:
        '''Standard D-Bus API for getting all property values'''

        self.log(f'GetAll {self.path} {interface_name}')

        if not interface_name:
            interface_name = self.interface
        try:
            return self.props[interface_name]
        except KeyError as e:
            raise dbus.exceptions.DBusException(
                'no such interface ' + interface_name,
                name=self.interface + '.UnknownInterface') from e

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ssv', out_signature='')
    def Set(self, interface_name: str, property_name: str, value: Any, *_, **__) -> None:
        '''Standard D-Bus API for setting a property value'''

        self.log(f'Set {self.path} {interface_name}.{property_name}{_format_args((value,))}')

        try:
            iface_props = self.props[interface_name]
        except KeyError as e:
            raise dbus.exceptions.DBusException(
                'no such interface ' + interface_name,
                name=self.interface + '.UnknownInterface') from e

        if property_name not in iface_props:
            raise dbus.exceptions.DBusException(
                'no such property ' + property_name,
                name=self.interface + '.UnknownProperty')

        iface_props[property_name] = value

        self.EmitSignal('org.freedesktop.DBus.Properties',
                        'PropertiesChanged',
                        'sa{sv}as',
                        [interface_name,
                         dbus.Dictionary({property_name: value}, signature='sv'),
                         dbus.Array([], signature='s')
                        ])

    @dbus.service.method(MOCK_IFACE,
                         in_signature='ssa{sv}a(ssss)',
                         out_signature='')
    def AddObject(self, path: str, interface: str, properties: PropsType, methods: List[MethodType]) -> None:
        '''Dynamically add a new D-Bus object to the mock

        path: D-Bus object path
        interface: Primary D-Bus interface name of this object (where
                   properties and methods will be put on)
        properties: A property_name (string) → value map with initial
                    properties on "interface"
        methods: An array of 4-tuples (name, in_sig, out_sig, code) describing
                 methods to add to "interface"; see AddMethod() for details of
                 the tuple values

        If this is a D-Bus ObjectManager instance, the InterfacesAdded signal
        will *not* be emitted for the object automatically; it must be emitted
        manually if desired. This is because AddInterface may be called after
        AddObject, but before the InterfacesAdded signal should be emitted.

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
            raise dbus.exceptions.DBusException(f'object {path} already exists', name='org.freedesktop.DBus.Mock.NameError')

        obj = DBusMockObject(self.bus_name,
                             path,
                             interface,
                             properties)
        # make sure created objects inherit the log file stream
        obj.logfile = self.logfile
        obj.object_manager = self.object_manager
        obj.is_logfile_owner = False
        obj.AddMethods(interface, methods)

        objects[path] = obj

    @dbus.service.method(MOCK_IFACE,
                         in_signature='s',
                         out_signature='')
    def RemoveObject(self, path: str) -> None:  # pylint: disable=no-self-use
        '''Remove a D-Bus object from the mock

        As with AddObject, this will *not* emit the InterfacesRemoved signal if
        it’s an ObjectManager instance.
        '''
        try:
            objects[path].remove_from_connection()
            del objects[path]
        except KeyError as e:
            raise dbus.exceptions.DBusException(
                f'object {path} does not exist',
                name='org.freedesktop.DBus.Mock.NameError') from e

    @dbus.service.method(MOCK_IFACE,
                         in_signature='', out_signature='')
    def Reset(self) -> None:
        '''Reset the mock object state.

        Remove all mock objects from the bus and tidy up so the state is as if
        python-dbusmock had just been restarted. If the mock object was
        originally created with a template (from the command line, the Python
        API or by calling AddTemplate over D-Bus), it will be
        re-instantiated with that template.
        '''
        # Clear other existing objects.
        for obj_name, obj in objects.items():
            if obj_name != self.path:
                obj.remove_from_connection()
        objects.clear()

        # Reinitialise our state. Carefully remove new methods from our dict;
        # they don't not actually exist if they are a statically defined
        # template function
        for method_name in self.methods[self.interface]:
            try:
                delattr(self.__class__, method_name)
            except AttributeError:
                pass

        self._reset({})

        if self._template is not None:
            self.AddTemplate(self._template, self._template_parameters)

        objects[self.path] = self

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sssss',
                         out_signature='')
    def AddMethod(self, interface, name: str, in_sig: str, out_sig: str, code: str) -> None:
        '''Dynamically add a method to this object

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

              For keeping state across method calls, you are free to use normal
              Python members of the "self" object, which will be persistent for
              the whole mock's life time. E. g. you can have a method with
              "self.my_state = True", and another method that returns it with
              "ret = self.my_state".

              Methods can raise exceptions in the usual way, in particular
              dbus.exceptions.DBusException:
              <https://dbus.freedesktop.org/doc/dbus-python/dbus.html#dbus.DBusException>

              When specifying '', the method will not do anything (except
              logging) and return None.


        This is meant for adding a method to a mock at runtime, from any programming language.
        You can also use it in templates in the load() function.

        For implementing non-trivial and static methods in templates, it is recommended to
        implement them in the normal dbus-python way with using the @dbus.service.method
        decorator instead.
        '''
        # pylint: disable=protected-access

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
        dbus_method._dbus_args = [f'arg{i}' for i in range(1, n_args + 1)]

        # for convenience, add mocked methods on the primary interface as
        # callable methods
        if interface == self.interface:
            setattr(self.__class__, name, dbus_method)

        self.methods.setdefault(interface, {})[str(name)] = (in_sig, out_sig, code, dbus_method)

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sa(ssss)',
                         out_signature='')
    def AddMethods(self, interface: str, methods: List[MethodType]) -> None:
        '''Add several methods to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the method to the object's main
                   interface (as specified on construction).
        methods: list of 4-tuples (name, in_sig, out_sig, code) describing one
                 method each. See AddMethod() for details of the tuple values.
        '''
        for method in methods:
            self.AddMethod(interface, *method)

    def _set_property(self, interface, name, value):
        # copy.copy removes one level of variant-ness, which means that the
        # types get exported in introspection data correctly, but we can't do
        # this for container types.
        if not isinstance(value, (dbus.Dictionary, dbus.Array)):
            value = copy.copy(value)

        self.props.setdefault(interface, {})[name] = value

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sa{sv}',
                         out_signature='')
    def UpdateProperties(self, interface: str, properties: PropsType) -> None:
        '''Update properties on this object and send a PropertiesChanged signal

        interface: D-Bus interface to update this to. For convenience you can
                   specify '' here to add the property to the object's main
                   interface (as specified on construction).
        properties: A property_name (string) → value map
        '''
        changed_props = {}

        for name, value in properties.items():
            if not interface:
                interface = self.interface
            if name not in self.props.get(interface, {}):
                raise dbus.exceptions.DBusException(f'property {name} not found', name=interface + '.NoSuchProperty')

            self._set_property(interface, name, value)
            changed_props[name] = _wrap_in_dbus_variant(value)

        self.EmitSignal(dbus.PROPERTIES_IFACE, 'PropertiesChanged', 'sa{sv}as', [
            interface, changed_props, []])

    @dbus.service.method(MOCK_IFACE,
                         in_signature='ssv',
                         out_signature='')
    def AddProperty(self, interface: str, name: str, value: Any) -> None:
        '''Add property to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the property to the object's main
                   interface (as specified on construction).
        name: Property name.
        value: Property value.
        '''
        if not interface:
            interface = self.interface
        if name in self.props.get(interface, {}):
            raise dbus.exceptions.DBusException(f'property {name} already exists', name=self.interface + '.PropertyExists')

        self._set_property(interface, name, value)

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sa{sv}',
                         out_signature='')
    def AddProperties(self, interface: str, properties: PropsType) -> None:
        '''Add several properties to this object

        interface: D-Bus interface to add this to. For convenience you can
                   specify '' here to add the property to the object's main
                   interface (as specified on construction).
        properties: A property_name (string) → value map
        '''
        for k, v in properties.items():
            self.AddProperty(interface, k, v)

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sa{sv}',
                         out_signature='')
    def AddTemplate(self, template: str, parameters: PropsType) -> None:
        '''Load a template into the mock.

        python-dbusmock ships a set of standard mocks for common system
        services such as UPower and NetworkManager. With these the actual tests
        become a lot simpler, as they only have to set up the particular
        properties for the tests, and not the skeleton of common properties,
        interfaces, and methods.

        template: Name of the template to load or the full path to a *.py file
                  for custom templates. See "pydoc dbusmock.templates" for a
                  list of available templates from python-dbusmock package, and
                  "pydoc dbusmock.templates.NAME" for documentation about
                  template NAME.
        parameters: A parameter (string) → value (variant) map, for
                    parameterizing templates. Each template can define their
                    own, see documentation of that particular template for
                    details.
        '''
        try:
            module = load_module(template)
        except ImportError as e:
            raise dbus.exceptions.DBusException(f'Cannot add template {template}: {str(e)}',
                                                name='org.freedesktop.DBus.Mock.TemplateError')

        # If the template specifies this is an ObjectManager, set that up
        if hasattr(module, 'IS_OBJECT_MANAGER') and module.IS_OBJECT_MANAGER:
            self._set_up_object_manager()

        # pick out all D-Bus service methods and add them to our interface
        for symbol in dir(module):
            # pylint: disable=protected-access
            fn = getattr(module, symbol)
            if ('_dbus_interface' in dir(fn) and ('_dbus_is_signal' not in dir(fn) or not fn._dbus_is_signal)):
                fn = loggedmethod(self, fn)

                # for dbus-python compatibility, add methods as callables
                setattr(self.__class__, symbol, fn)
                self.methods.setdefault(fn._dbus_interface, {})[str(symbol)] = (
                    fn._dbus_in_signature,
                    fn._dbus_out_signature, '', fn
                )

        if parameters is None:
            parameters = {}

        module.load(self, parameters)
        # save the given template and parameters for re-instantiation on
        # Reset()
        self._template = template
        self._template_parameters = parameters

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sssav',
                         out_signature='')
    def EmitSignal(self, interface: str, name: str, signature: str, sigargs: Tuple[Any, ...]) -> None:
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
        # pylint: disable=protected-access
        if not interface:
            interface = self.interface

        args = _convert_args(signature, sigargs)

        fn = lambda self, *args: self.log(f'emit {self.path} {interface}.{name}{_format_args(args)}')
        fn.__name__ = str(name)
        dbus_fn = dbus.service.signal(interface)(fn)
        dbus_fn._dbus_signature = signature
        dbus_fn._dbus_args = [f'arg{i}' for i in range(1, len(args) + 1)]

        dbus_fn(self, *args)

    @dbus.service.method(MOCK_IFACE,
                         in_signature='',
                         out_signature='a(tsav)')
    def GetCalls(self) -> List[CallLogType]:
        '''List all the logged calls since the last call to ClearCalls().

        Return a list of (timestamp, method_name, args_list) tuples.
        '''
        return self.call_log

    @dbus.service.method(MOCK_IFACE,
                         in_signature='s',
                         out_signature='a(tav)')
    def GetMethodCalls(self, method: str) -> List[Tuple[int, Sequence[Any]]]:
        '''List all the logged calls of a particular method.

        Return a list of (timestamp, args_list) tuples.
        '''
        return [(row[0], row[2]) for row in self.call_log if row[1] == method]

    @dbus.service.method(MOCK_IFACE,
                         in_signature='',
                         out_signature='')
    def ClearCalls(self) -> None:
        '''Empty the log of mock call signatures.'''

        self.call_log = []

    @dbus.service.signal(MOCK_IFACE, signature='sav')
    def MethodCalled(self, name, args):
        '''Signal emitted for every called mock method.

        This is emitted for all mock method calls.  This can be used to confirm
        that a particular method was called with particular arguments, as an
        alternative to reading the mock's log or GetCalls().
        '''

    def object_manager_emit_added(self, path: str) -> None:
        '''Emit ObjectManager.InterfacesAdded signal'''

        if self.object_manager is not None:
            self.object_manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesAdded',
                                           'oa{sa{sv}}', [dbus.ObjectPath(path),
                                                          objects[path].props])

    def object_manager_emit_removed(self, path: str) -> None:
        '''Emit ObjectManager.InterfacesRemoved signal'''

        if self.object_manager is not None:
            self.object_manager.EmitSignal(OBJECT_MANAGER_IFACE, 'InterfacesRemoved',
                                           'oas', [dbus.ObjectPath(path),
                                                   objects[path].props])

    def mock_method(self, interface: str, dbus_method: str, in_signature: str, *m_args, **_) -> Any:
        '''Master mock method.

        This gets "instantiated" in AddMethod(). Execute the code snippet of
        the method and return the "ret" variable if it was set.
        '''
        # print('mock_method', dbus_method, self, in_signature, args, _, file=sys.stderr)

        try:
            args = _convert_args(in_signature, m_args)

            self.log(dbus_method + _format_args(args))
            self.call_log.append((int(time.time()), str(dbus_method), args))
            self.MethodCalled(dbus_method, args)

            # The code may be a Python 3 string to interpret, or may be a function
            # object (if AddMethod was called from within Python itself, rather than
            # over D-Bus).
            code = self.methods[interface][dbus_method][2]
            if code and isinstance(code, types.FunctionType):
                return code(self, *args)
            if code:
                loc = locals().copy()
                exec(code, globals(), loc)  # pylint: disable=exec-used
                if 'ret' in loc:
                    return loc['ret']
        except Exception as e:
            self.log(dbus_method + ' raised: ' + str(e))
            raise e

        return None

    def log(self, msg: str) -> None:
        '''Log a message, prefixed with a timestamp.

        If a log file was specified in the constructor, it is written there,
        otherwise it goes to stdout.
        '''
        if self.logfile:
            fd = self.logfile.fileno()
        else:
            fd = sys.stdout.fileno()

        os.write(fd, f'{time.time():.3f} {msg}\n'.encode('UTF-8'))

    @dbus.service.method(dbus.INTROSPECTABLE_IFACE,
                         in_signature='',
                         out_signature='s',
                         path_keyword='object_path',
                         connection_keyword='connection')
    def Introspect(self, object_path: str, connection: dbus.connection.Connection) -> str:
        '''Return XML description of this object's interfaces, methods and signals.

        This wraps dbus-python's Introspect() method to include the dynamic
        methods and properties.
        '''
        # _dbus_class_table is an indirect private member of dbus.service.Object that pylint fails to see
        # pylint: disable=no-member

        # temporarily add our dynamic methods
        cls = self.__class__.__module__ + '.' + self.__class__.__name__
        orig_interfaces = self._dbus_class_table[cls]

        mock_interfaces = orig_interfaces.copy()
        for iface, methods in self.methods.items():
            for method, impl in methods.items():
                mock_interfaces.setdefault(iface, {})[method] = impl[3]
        self._dbus_class_table[cls] = mock_interfaces

        xml = dbus.service.Object.Introspect(self, object_path, connection)

        tree = ElementTree.fromstring(xml)

        for name, name_props in self.props.items():
            # We might have properties for new interfaces we don't know about
            # yet. Try to find an existing <interface> node named after our
            # interface to append to, and create one if we can't.
            interface = tree.find(f".//interface[@name='{name}']")
            if interface is None:
                interface = ElementTree.Element("interface", {"name": name})
                tree.append(interface)

            for prop, val in name_props.items():
                if val is None:
                    # can't guess type from None, skip
                    continue
                elem = ElementTree.Element("property", {
                    "name": prop,
                    # We don't store the signature anywhere, so guess it.
                    "type": dbus.lowlevel.Message.guess_signature(val),
                    "access": "readwrite"})

                interface.append(elem)

        xml = ElementTree.tostring(tree, encoding='utf8', method='xml').decode('utf8')

        # restore original class table
        self._dbus_class_table[cls] = orig_interfaces

        return xml


# Overwrite dbus-python's _method_lookup(), as that offers no way to have the
# same method name on different interfaces
orig_method_lookup = dbus.service._method_lookup  # pylint: disable=protected-access


def _dbusmock_method_lookup(obj, method_name, dbus_interface):
    try:
        m = obj.methods[dbus_interface or obj.interface][method_name]
        return (m[3], m[3])
    except KeyError:
        return orig_method_lookup(obj, method_name, dbus_interface)


dbus.service._method_lookup = _dbusmock_method_lookup  # pylint: disable=protected-access


#
# Helper API for templates
#


def get_objects() -> KeysView[str]:
    '''Return all existing object paths'''

    return objects.keys()


def get_object(path) -> DBusMockObject:
    '''Return object for a given object path'''

    return objects[path]
