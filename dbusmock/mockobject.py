# coding: UTF-8
'''Mock D-BUS objects for test suites.'''

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
import importlib

# we do not use this ourselves, but mock methods often want to use this
import os
os  # pyflakes

import dbus
import dbus.service

# global path -> DBusMockObject mapping
objects = {}

MOCK_IFACE = 'org.freedesktop.DBus.Mock'

# stubs to keep code compatible with Python 2 and 3
if sys.version_info[0] >= 3:
    long = int
    unicode = str


def load_module(name):
    if os.path.exists(name) and os.path.splitext(name)[1] == '.py':
        sys.path.insert(0, os.path.dirname(os.path.abspath(name)))
        try:
            m = os.path.splitext(os.path.basename(name))[0]
            module = importlib.import_module(m)
        finally:
            sys.path.pop(0)

        return module

    return importlib.import_module('dbusmock.templates.' + name)


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
                 if None, logging will be written to stdout. Note that you can
                 also query the called methods over D-BUS with GetCalls() and
                 GetMethodCalls().
        '''
        dbus.service.Object.__init__(self, bus_name, path)

        self.bus_name = bus_name
        self.interface = interface
        # interface -> name -> value
        self.props = {}
        if props is None:
            props = {}
        self.props[interface] = props

        # interface -> name -> (in_signature, out_signature, code, dbus_wrapper_fn)
        self.methods = {interface: {}}

        if logfile:
            self.logfile = open(logfile, 'w')
        else:
            self.logfile = None
        self.call_log = []

    def __del__(self):
        if self.logfile:
            self.logfile.close()

    @dbus.service.method(dbus.PROPERTIES_IFACE,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        '''Standard D-Bus API for getting a property value'''

        if not interface_name:
            interface_name = self.interface
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

        if not interface_name:
            interface_name = self.interface
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

    @dbus.service.method(MOCK_IFACE,
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
        # make sure created objects inherit the log file stream
        obj.logfile = self.logfile
        obj.AddMethods(interface, methods)

        objects[path] = obj

    @dbus.service.method(MOCK_IFACE,
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

    @dbus.service.method(MOCK_IFACE,
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

              For keeping state across method calls, you are free to use normal
              Python members of the "self" object, which will be persistant for
              the whole mock's life time. E. g. you can have a method with
              "self.my_state = True", and another method that returns it with
              "ret = self.my_state".

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

    @dbus.service.method(MOCK_IFACE,
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

    @dbus.service.method(MOCK_IFACE,
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

    @dbus.service.method(MOCK_IFACE,
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

    @dbus.service.method(MOCK_IFACE,
                         in_signature='sa{sv}',
                         out_signature='')
    def AddTemplate(self, template, parameters):
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
            raise dbus.exceptions.DBusException('Cannot add template %s: %s' % (template, str(e)))

        # pick out all D-BUS service methods and add them to our interface
        for symbol in dir(module):
            fn = getattr(module, symbol)
            if '_dbus_interface' in dir(fn):
                setattr(self.__class__, symbol, fn)

        if parameters is None:
            parameters = {}

        module.load(self, parameters)

    @dbus.service.method(MOCK_IFACE,
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

        fn = lambda self, *args: self.log('emit %s.%s%s' % (interface, name, self.format_args(args)))
        fn.__name__ = str(name)
        dbus_fn = dbus.service.signal(interface)(fn)
        dbus_fn._dbus_signature = signature
        dbus_fn._dbus_args = ['arg%i' % i for i in range(1, len(args) + 1)]

        dbus_fn(self, *args)

    @dbus.service.method(MOCK_IFACE,
                         in_signature='',
                         out_signature='a(tsav)')
    def GetCalls(self):
        '''List all the logged calls since the last call to ClearCalls().

        Return a list of (timestamp, method_name, args_list) tuples.
        '''
        return self.call_log

    @dbus.service.method(MOCK_IFACE,
                         in_signature='s',
                         out_signature='a(tav)')
    def GetMethodCalls(self, method):
        '''List all the logged calls of a particular method.

        Return a list of (timestamp, args_list) tuples.
        '''
        return [(row[0], row[2]) for row in self.call_log if row[1] == method]

    @dbus.service.method(MOCK_IFACE,
                         in_signature='',
                         out_signature='')
    def ClearCalls(self):
        '''Empty the log of mock call signatures.'''

        self.call_log = []

    @dbus.service.signal(MOCK_IFACE, signature='sav')
    def MethodCalled(self, name, args):
        pass

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

        self.log(dbus_method + self.format_args(args))
        self.call_log.append((int(time.time()), str(dbus_method), args))
        self.MethodCalled(dbus_method, args)

        code = self.methods[interface][dbus_method][2]
        if code:
            loc = locals().copy()
            exec(code, globals(), loc)
            if 'ret' in loc:
                return loc['ret']

    def format_args(self, args):
        '''Format a D-BUS argument tuple into an appropriate logging string.'''

        def format_arg(a):
            if isinstance(a, dbus.Boolean):
                return str(bool(a))
            if isinstance(a, dbus.Byte):
                return str(int(a))
            if isinstance(a, int) or isinstance(a, long):
                return str(a)
            if isinstance(a, str) or isinstance(a, unicode):
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

        xml = dbus.service.Object.Introspect(self, object_path, connection)

        # restore original class table
        self._dbus_class_table[cls] = orig_interfaces

        return xml

#
# Helper API for templates
#


def get_objects():
    '''Return all existing object paths'''

    return objects.keys()


def get_object(path):
    '''Return object for a given object path'''

    return objects[path]
