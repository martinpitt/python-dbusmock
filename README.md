![CI status](https://github.com/martinpitt/python-dbusmock/actions/workflows/tests.yml/badge.svg)

python-dbusmock
===============

## Purpose

With this program/Python library you can easily create mock objects on
D-Bus. This is useful for writing tests for software which talks to
D-Bus services such as upower, systemd, logind, gnome-session or others,
and it is hard (or impossible without root privileges) to set the state
of the real services to what you expect in your tests.

Suppose you want to write tests for a desktop environment's power management:
You want to verify that after the configured idle time the program suspends the
machine. So your program calls `org.freedesktop.login1.Manager.Suspend()` on
the system D-Bus.

Now, your test suite should not really talk to the actual system D-Bus and
the real systemd; a `make check` that suspends your machine will not be
considered very friendly by most people, and if you want to run this in
continuous integration test servers or package build environments, chances
are that your process does not have the privilege to suspend, or there is
no system bus or running systemd to begin with. Likewise, there is no way
for an user process to forcefully set the system/seat idle flag in logind,
so your tests cannot set up the expected test environment on the real
daemon.

That's where mock objects come into play: They look like the real API
(or at least the parts that you actually need), but they do not actually
do anything (or only some action that you specify yourself). You can
configure their state, behaviour and responses as you like in your test,
without making any assumptions about the real system status.

When using a local system/session bus, you can do unit or integration
testing without needing root privileges or disturbing a running system.
The Python API offers some convenience functions like
`start_session_bus()` and `start_system_bus()` for this, in a
`DBusTestCase` class (subclass of the standard `unittest.TestCase`) or
alternatively as a `@pytest.fixture`.

You can use this with any programming language, as you can run the
mocker as a normal program. The actual setup of the mock (adding
objects, methods, properties, and signals) all happen via D-Bus methods
on the `org.freedesktop.DBus.Mock` interface. You just don't have the
convenience D-Bus launch API that way.

## Simple example using Python's unittest

Picking up the above example about mocking systemd-logind's `Suspend()`
method, this is how you would set up a mock logind in your test case:

```python
import subprocess
import unittest

import dbus

import dbusmock


class TestMyProgram(dbusmock.DBusTestCase):
    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(system_bus=True)

    def setUp(self):
        self.p_mock = self.spawn_server('org.freedesktop.login1',
                                        '/org/freedesktop/login1',
                                        'org.freedesktop.login1.Manager',
                                        system_bus=True,
                                        stdout=subprocess.PIPE)
        self.addCleanup(self.p_mock.wait)
        self.addCleanup(self.p_mock.terminate)
        self.addCleanup(self.p_mock.stdout.close)

        # Get a proxy for the logind object's Mock interface
        self.dbus_logind_mock = dbus.Interface(self.dbus_con.get_object(
            'org.freedesktop.login1', '/org/freedesktop/login1'),
            dbusmock.MOCK_IFACE)

        self.dbus_logind_mock.AddMethod('', 'Suspend', 'b', '', '')

    def test_suspend_on_idle(self):
        # run your program in a way that should trigger one suspend call
        # represented here as direct D-Bus call
        subprocess.check_call(
            ["busctl", "call", "org.freedesktop.login1",
            "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            "Suspend", "b", "false"])

        # now check the log that we got one Suspend() call
        self.assertRegex(self.p_mock.stdout.readline(), b'^[0-9.]+ Suspend False$')
```

Let's walk through:

 -   We derive our tests from `dbusmock.DBusTestCase` instead of
     `unittest.TestCase` directly, to make use of the convenience API
     to start a local system bus.

 -   `setUpClass()` starts a local system bus, and makes a connection
     to it available to all methods as `dbus_con`. `True` means that we
     connect to the system bus, not the session bus. We can use the
     same bus for all tests, so doing this once in `setUpClass()`
     instead of `setUp()` is enough.

 -   `setUp()` spawns the mock D-Bus server process for an initial
     `/org/freedesktop/login1` object with an `org.freedesktop.login1`
     D-Bus interface on the system bus. We capture its stdout to be
     able to verify that methods were called.

     We then call `org.freedesktop.DBus.Mock.AddMethod()` to add a
     `Suspend()` method to our new object to the default D-Bus
     interface. This will not do anything (except log its call to
     stdout). It takes no input arguments, returns nothing, and does
     not run any custom code.

     We use `addCleanup()` to register cleanup handlers that will
     stop our mock D-Bus server after each test. This ensures each
     test case has a fresh and clean logind mock instance. Of course
     you can also set up everything in `setUpClass()` if tests
     do not interfere with each other on setting up the mock.

 -   `test_suspend_on_idle()` is the actual test case. It needs to run
     your program in a way that should trigger one suspend call. For this
     example this is represented by doing just a direct D-Bus call using
     `busctl`.

     That `Suspend()` call is now being served by our mock instead of the real
     logind, there will not be any actual machine suspend. Our mock process
     will log the method call together with a time stamp; you can use the
     latter for doing timing related tests, but we just ignore it here.

## Simple example using pytest

The same functionality as above but instead using the pytest fixture provided
by this package.

```python
# Enable dbusmock's pytest fixtures (can also go in conftest.py)
pytest_plugins = "dbusmock.pytest_fixtures"

import subprocess

import dbus

import dbusmock


def test_suspend_on_idle(dbusmock_system):
    # Spawn the mock D-Bus server for logind on the system bus
    with dbusmock.SpawnedMock.spawn_for_name(
        'org.freedesktop.login1',
        '/org/freedesktop/login1',
        'org.freedesktop.login1.Manager',
        dbusmock.BusType.SYSTEM,
        stdout=subprocess.PIPE) as p_mock:

        # Get a proxy for the logind object's Mock interface
        obj_logind = p_mock.obj
        obj_logind.AddMethod('', 'Suspend', 'b', '', '', interface_name=dbusmock.MOCK_IFACE)

        # Run your program in a way that should trigger one suspend call
        # represented here as direct D-Bus call
        subprocess.check_call(
            ["busctl", "call", "org.freedesktop.login1",
            "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            "Suspend", "b", "false"])

        # Check the log that we got one Suspend() call
        assert b'Suspend False\n' in p_mock.stdout.readline()
```

Let's walk through:

- We enable dbusmock's pytest fixtures with `pytest_plugins = "dbusmock.pytest_fixtures"`.
  This makes fixtures like `dbusmock_system` and `dbusmock_session` available to your
  tests. In a real project, you would typically put this line in your `conftest.py`
  instead of in each test file.

- We import the `dbusmock_system` fixture from dbusmock which provides us
  with a system bus started for our test case. Even though we don't use it
  directly in this simple example, it ensures the test environment is set up.

- `test_suspend_on_idle()` is the actual test. It uses
  `SpawnedMock.spawn_for_name()` to spawn the mock D-Bus server process for
  `/org/freedesktop/login1` object with `org.freedesktop.login1.Manager`
  interface. We capture its stdout to verify that methods were called.

  We then call `org.freedesktop.DBus.Mock.AddMethod()` to add a `Suspend()`
  method to our new logind mock object to the default D-Bus interface. This
  will not do anything (except log its call to stdout). It takes one boolean
  input argument, returns nothing, and does not run any custom code.

  Exactly like in the unittest example above, we then run our program in a way that
  should trigger one suspend call. For this example this is again represented
  by doing just a direct D-Bus call using `busctl`. The log of the call gets
  asserted.

  The context manager automatically terminates the mock server process after
  the test completes.

## Simple example from shell

We use the actual session bus for this example. You can use
`dbus-run-session` to start a private one as well if you want, but that
is not part of the actual mocking.

So let's start a mock at the D-Bus name `com.example.Foo` with an
initial "main" object on path /, with the main D-Bus interface
`com.example.Foo.Manager`:

    python3 -m dbusmock com.example.Foo / com.example.Foo.Manager

On another terminal, let's first see what it does:

    gdbus introspect --session -d com.example.Foo -o /

You'll see that it supports the standard D-Bus `Introspectable` and
`Properties` interfaces, as well as the `org.freedesktop.DBus.Mock`
interface for controlling the mock, but no "real" functionality yet.
So let's add a method:

    gdbus call --session -d com.example.Foo -o / -m org.freedesktop.DBus.Mock.AddMethod '' Ping '' '' ''

Now you can see the new method in `introspect`, and call it:

    gdbus call --session -d com.example.Foo -o / -m com.example.Foo.Manager.Ping

The mock process in the other terminal will log the method call with a
time stamp, and you'll see something like `1348832614.970 Ping`.

Now add another method with two int arguments and a return value and
call it:

    gdbus call --session -d com.example.Foo -o / -m org.freedesktop.DBus.Mock.AddMethod \
        '' Add 'ii' 'i' 'ret = args[0] + args[1]'
    gdbus call --session -d com.example.Foo -o / -m com.example.Foo.Manager.Add 2 3

This will print `(5,)` as expected (remember that the return value is
always a tuple), and again the mock process will log the Add method
call.

You can do the same operations in e. g. d-feet or any other D-Bus
language binding.

## Interactive debugging

It's possible to use dbus-mock to run interactive sessions using something like:

    python3 -m dbusmock com.example.Foo / com.example.Foo.Manager -e $SHELL

Where a shell session with the defined mocks is set and others can be added.

Or more complex ones such as:

    python3 -m dbusmock --session -t upower -e \
      python3 -m dbusmock com.example.Foo / com.example.Foo.Manager -e \
        gdbus introspect --session -d com.example.Foo -o /

## Logging

Usually you want to verify which methods have been called on the mock
with which arguments. There are three ways to do that:

 -   By default, the mock process writes the call log to stdout.
 -   You can call the mock process with the `-l`/`--logfile` argument,
     or specify a log file object in the `spawn_server()` method if you
     are using Python.
 -   You can use the `GetCalls()`, `GetMethodCalls()` and
     `ClearCalls()` methods on the `org.freedesktop.DBus.Mock` D-Bus
     interface to get an array of tuples describing the calls.

## Templates

Some D-Bus services are commonly used in test suites, such as UPower or
NetworkManager. python-dbusmock provides "templates" which set up the
common structure of these services (their main objects, properties, and
methods) so that you do not need to carry around this common code, and
only need to set up the particular properties and specific D-Bus objects
that you need. These templates can be parameterized for common
customizations, and they can provide additional convenience methods on
the `org.freedesktop.DBus.Mock` interface to provide more abstract
functionality like "add a battery".

For example, for starting a server with the `upower` template in
Python you can run

    (self.p_mock, self.obj_upower) = self.spawn_server_template(
        'upower', {'OnBattery': True}, stdout=subprocess.PIPE)

or load a template into an already running server with the
`AddTemplate()` method; this is particularly useful if you are not using
Python:

    python3 -m dbusmock --system org.freedesktop.UPower /org/freedesktop/UPower org.freedesktop.UPower

    gdbus call --system -d org.freedesktop.UPower -o /org/freedesktop/UPower -m org.freedesktop.DBus.Mock.AddTemplate 'upower' '{"OnBattery": <true>}'

This creates all expected properties such as `DaemonVersion`, and
changes the default for one of them (`OnBattery`) through the (optional)
parameters dict.

If you do not need to specify parameters, you can do this in a simpler
way with

    python3 -m dbusmock --template upower

The template does not create any devices by default. You can add some
with the template's convenience methods like

    ac_path = self.dbusmock.AddAC('mock_AC', 'Mock AC')
    bt_path = self.dbusmock.AddChargingBattery('mock_BAT', 'Mock Battery', 30.0, 1200)

or calling `AddObject()` yourself with the desired properties, of
course.

Templates commonly implement some non-trivial functionality with actual Python
methods and the standard [dbus-python](https://dbus.freedesktop.org/doc/dbus-python/)
[`@dbus.service.method`](https://dbus.freedesktop.org/doc/dbus-python/dbus.service.html#dbus.service.method)
decorator.

To build your own template, you can copy
[dbusmock/templates/SKELETON](./dbusmock/templates/SKELETON) to your
new template file name and replace `CHANGEME` with the actual code/values.
Look at [dbusmock/templates/upower.py](./dbusmock/templates/upower.py) for
a real-life implementation.

A template can be loaded from these locations:

 * Provide a path to its `.py` file. This is intended for running tests out of
   git/build trees with very project specific or unstable templates.

 * From [`$XDG_DATA_DIRS/python-dbusmock/templates/`*name*`.py`](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html).
   This is intended for shipping reusable templates in distribution development
   packages. Load them by module name.

 * python-dbusmock [ships a set of widely applicable templates](./dbusmock/templates/)
   which are collaboratively maintained, like the `upower` one in the example
   above. Load them by module name.

## More Examples

Have a look at the test suite for two real-live use cases:

 -   `tests/test_upower.py` simulates upowerd, in a more complete way
     than in above example and using the `upower` template. It verifies
     that `upower --dump` is convinced that it's talking to upower.
 -   `tests/test_api.py` runs a mock on the session bus and exercises
     all available functionality, such as adding additional objects,
     properties, multiple methods, input arguments, return values, code
     in methods, sending signals, raising exceptions, and introspection.

## Documentation

The `dbusmock` module has extensive documentation built in, which you
can read with e. g. `pydoc3 dbusmock` or online at
https://martinpitt.github.io/python-dbusmock/

`pydoc3 dbusmock.DBusMockObject` shows the D-Bus API of the mock object,
i. e. methods like `AddObject()`, `AddMethod()` etc. which are used to
set up your mock object.

`pydoc3 dbusmock.DBusTestCase` shows the convenience Python API for
writing test cases with local private session/system buses and launching
the server.

`pydoc3 dbusmock.templates` shows all available templates.

`pydoc3 dbusmock.templates.NAME` shows the documentation and available
parameters for the `NAME` template.

`python3 -m dbusmock --help` shows the arguments and options for running
the mock server as a program.

## Development

python-dbusmock is hosted on https://github.com/martinpitt/python-dbusmock

Run the unit tests with `python3 -m unittest` or `pytest`.

In CI, the unit tests run in containers. You can run them locally with e.g.

    tests/run registry.fedoraproject.org/fedora:latest

Check the [unit-tests GitHub workflow](.github/workflows/tests.yml) for the
operating systems/container images on which python-dbusmock is tested and
supported.

To debug failures interactively, run

    DEBUG=1 tests/run [image]

which will sleep on failures. You can then attach to the running container
image with e.g. `podman exec -itl bash`. The `/source` directory is mounted from the
host, i.e. edit files in your normal git checkout outside of the container, and
re-run all tests in the container shell like above. You can also run a specific
test:

    python3 -m unittest tests.test_api.TestAPI.test_onearg_ret
