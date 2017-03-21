python-dbusmock
===============

Purpose
-------
With this program/Python library you can easily create mock objects on D-Bus.
This is useful for writing tests for software which talks to D-Bus services
such as upower, systemd, logind, gnome-session or others, and it is hard
(or impossible without root privileges) to set the state of the real services
to what you expect in your tests.

Suppose you want to write tests for gnome-settings-daemon's power plugin, or
another program that talks to upower. You want to verify that after the
configured idle time the program suspends the machine. So your program calls
``org.freedesktop.UPower.Suspend()`` on the system D-Bus.

Now, your test suite should not really talk to the actual system D-Bus and the
real upower; a ``make check`` that suspends your machine will not be considered
very friendly by most people, and if you want to run this in continuous
integration test servers or package build environments, chances are that your
process does not have the privilege to suspend, or there is no system bus or
upower to begin with. Likewise, there is no way for an user process to
forcefully set the system/seat idle flag in logind, so your
tests cannot set up the expected test environment on the real daemon.

That's where mock objects come into play: They look like the real API (or at
least the parts that you actually need), but they do not actually do anything
(or only some action that you specify yourself). You can configure their
state, behaviour and responses as you like in your test, without making any
assumptions about the real system status.

When using a local system/session bus, you can do unit or integration testing
without needing root privileges or disturbing a running system. The Python API
offers some convenience functions like ``start_session_bus()`` and
``start_system_bus()`` for this, in a ``DBusTestCase`` class (subclass of the
standard ``unittest.TestCase``).

You can use this with any programming language, as you can run the mocker as a
normal program. The actual setup of the mock (adding objects, methods,
properties, and signals) all happen via D-Bus methods on the
``org.freedesktop.DBus.Mock`` interface. You just don't have the convenience
D-Bus launch API that way.


Simple example in Python
------------------------
Picking up the above example about mocking upower's ``Suspend()`` method, this
is how you would set up a mock upower in your test case:

.. code-block:: python

  import dbus
  import dbusmock

  class TestMyProgram(dbusmock.DBusTestCase):
      @classmethod
      def setUpClass(klass):
          klass.start_system_bus()
          klass.dbus_con = klass.get_dbus(system_bus=True)

      def setUp(self):
          self.p_mock = self.spawn_server('org.freedesktop.UPower',
                                          '/org/freedesktop/UPower',
                                          'org.freedesktop.UPower',
                                          system_bus=True,
                                          stdout=subprocess.PIPE)

          # Get a proxy for the UPower object's Mock interface
          self.dbus_upower_mock = dbus.Interface(self.dbus_con.get_object(
              'org.freedesktop.UPower', '/org/freedesktop/UPower'),
              dbusmock.MOCK_IFACE)

          self.dbus_upower_mock.AddMethod('', 'Suspend', '', '', '')

      def tearDown(self):
          self.p_mock.terminate()
          self.p_mock.wait()

      def test_suspend_on_idle(self):
          # run your program in a way that should trigger one suspend call

          # now check the log that we got one Suspend() call
          self.assertRegex(self.p_mock.stdout.readline(), b'^[0-9.]+ Suspend$')

Let's walk through:

 - We derive our tests from ``dbusmock.DBusTestCase`` instead of
   ``unittest.TestCase`` directly, to make use of the convenience API to start
   a local system bus.

 - ``setUpClass()`` starts a local system bus, and makes a connection to it available
   to all methods as ``dbus_con``. ``True`` means that we connect to the
   system bus, not the session bus. We can use the same bus for all tests, so
   doing this once in ``setUpClass()`` instead of ``setUp()`` is enough.

 - ``setUp()`` spawns the mock D-Bus server process for an initial
   ``/org/freedesktop/UPower`` object with an ``org.freedesktop.UPower`` D-Bus
   interface on the system bus. We capture its stdout to be able to verify that
   methods were called.

   We then call ``org.freedesktop.DBus.Mock.AddMethod()`` to add a
   ``Suspend()`` method to our new object to the default D-Bus interface. This
   will not do anything (except log its call to stdout). It takes no input
   arguments, returns nothing, and does not run any custom code.

 - ``tearDown()`` stops our mock D-Bus server again. We do this so that each
   test case has a fresh and clean upower instance, but of course you can also
   set up everything in ``setUpClass()`` if tests do not interfere with each
   other on setting up the mock.

 - ``test_suspend_on_idle()`` is the actual test case. It needs to run your
   program in a way that should trigger one suspend call. Your program will
   try to call ``Suspend()``, but as that's now being served by our mock
   instead of upower, there will not be any actual machine suspend. Our
   mock process will log the method call together with a time stamp; you can
   use the latter for doing timing related tests, but we just ignore it here.

Simple example from shell
-------------------------

We use the actual session bus for this example. You can use ``dbus-launch`` to
start a private one as well if you want, but that is not part of the actual
mocking.

So let's start a mock at the D-Bus name ``com.example.Foo`` with an initial
"main" object on path /, with the main D-Bus interface
``com.example.Foo.Manager``:

::

  python3 -m dbusmock com.example.Foo / com.example.Foo.Manager

On another terminal, let's first see what it does:

::

  gdbus introspect --session -d com.example.Foo -o /

You'll see that it supports the standard D-Bus ``Introspectable`` and
``Properties`` interfaces, as well as the ``org.freedesktop.DBus.Mock``
interface for controlling the mock, but no "real" functionality yet. So let's
add a method:

::

  gdbus call --session -d com.example.Foo -o / -m org.freedesktop.DBus.Mock.AddMethod '' Ping '' '' ''

Now you can see the new method in ``introspect``, and call it:

::

  gdbus call --session -d com.example.Foo -o / -m com.example.Foo.Manager.Ping

The mock process in the other terminal will log the method call with a time
stamp, and you'll see something like ``1348832614.970 Ping``.

Now add another method with two int arguments and a return value and call it:

::

  gdbus call --session -d com.example.Foo -o / -m org.freedesktop.DBus.Mock.AddMethod \
      '' Add 'ii' 'i' 'ret = args[0] + args[1]'
  gdbus call --session -d com.example.Foo -o / -m com.example.Foo.Manager.Add 2 3

This will print ``(5,)`` as expected (remember that the return value is always
a tuple), and again the mock process will log the Add method call.

You can do the same operations in e. g. d-feet or any other D-Bus language
binding.

Logging
-------
Usually you want to verify which methods have been called on the mock with
which arguments. There are three ways to do that:

 - By default, the mock process writes the call log to stdout.

 - You can call the mock process with the ``-l``/``--logfile`` argument, or
   specify a log file object in the ``spawn_server()`` method  if you are using
   Python.

 - You can use the ``GetCalls()``, ``GetMethodCalls()`` and ``ClearCalls()``
   methods on the ``org.freedesktop.DBus.Mock`` D-BUS interface to get an array
   of tuples describing the calls.


Templates
---------
Some D-BUS services are commonly used in test suites, such as UPower or
NetworkManager. python-dbusmock provides "templates" which set up the common
structure of these services (their main objects, properties, and methods) so
that you do not need to carry around this common code, and only need to set up
the particular properties and specific D-BUS objects that you need. These
templates can be parameterized for common customizations, and they can provide
additional convenience methods on the ``org.freedesktop.DBus.Mock`` interface
to provide more abstract functionality like "add a battery".

For example, for starting a server with the "upower" template in Python you can
run

::

  (self.p_mock, self.obj_upower) = self.spawn_server_template(
      'upower', {'OnBattery': True}, stdout=subprocess.PIPE)

or load a template into an already running server with the ``AddTemplate()``
method; this is particularly useful if you are not using Python:

::

  python3 -m dbusmock --system org.freedesktop.UPower /org/freedesktop/UPower org.freedesktop.UPower

  gdbus call --system -d org.freedesktop.UPower -o /org/freedesktop/UPower -m org.freedesktop.DBus.Mock.AddTemplate 'upower' '{"OnBattery": <true>}'

This creates all expected properties such as ``DaemonVersion``, and changes the
default for one of them (``OnBattery``) through the (optional) parameters dict.

If you do not need to specify parameters, you can do this in a simpler way with

::

  python3 -m dbusmock --template upower

The template does not create any devices by default. You can add some with
the template's convenience methods like

::

  ac_path = self.dbusmock.AddAC('mock_AC', 'Mock AC')
  bt_path = self.dbusmock.AddChargingBattery('mock_BAT', 'Mock Battery', 30.0, 1200)

or calling ``AddObject()`` yourself with the desired properties, of course.

If you want to contribute a template, look at dbusmock/templates/upower.py for
a real-life implementation. You can copy dbusmock/templates/SKELETON to your
new template file name and replace "CHANGEME" with the actual code/values.


More Examples
-------------
Have a look at the test suite for two real-live use cases:

 - ``tests/test_upower.py`` simulates upowerd, in a more complete way than in
   above example and using the ``upower`` template. It verifies that
   ``upower --dump`` is convinced that it's talking to upower.

 - ``tests/test_consolekit.py`` simulates ConsoleKit and verifies that
   ``ck-list-sessions`` works with the mock.

 - ``tests/test_api.py`` runs a mock on the session bus and exercises all
   available functionality, such as adding additional objects, properties,
   multiple methods, input arguments, return values, code in methods, raising
   signals, and introspection.


Documentation
-------------
The ``dbusmock`` module has extensive documentation built in, which you can
read with e. g. ``pydoc3 dbusmock``.

``pydoc3 dbusmock.DBusMockObject`` shows the D-Bus API of the mock object,
i. e. methods like ``AddObject()``, ``AddMethod()`` etc. which are used to set
up your mock object.

``pydoc3 dbusmock.DBusTestCase`` shows the convenience Python API for writing
test cases with local private session/system buses and launching the server.

``pydoc3 dbusmock.templates`` shows all available templates.

``pydoc3 dbusmock.templates.NAME`` shows the documentation and available
parameters for the ``NAME`` template.

``python3 -m dbusmock --help`` shows the arguments and options for running the
mock server as a program.


Development
-----------
python-dbusmock is hosted on github:

  https://github.com/martinpitt/python-dbusmock

Feedback
--------
For feature requests and bugs, please file reports at one of:

  https://github.com/martinpitt/python-dbusmock/issues
  https://bugs.launchpad.net/python-dbusmock
