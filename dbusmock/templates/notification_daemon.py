"""notification-daemon mock template

This creates the expected methods and properties of the notification-daemon
services, but no devices. You can specify non-default capabilities in
"parameters".


Testing applications
--------------------

Start the template on a private session bus before starting the application
under test. Importing the template alone does not start a service. Processes
started inside the private bus context inherit its ``DBUS_SESSION_BUS_ADDRESS``;
already connected clients can retain their previous connection.

See ``TestNotificationActions.test_notification_action`` in
``tests/test_notification_daemon.py`` for a complete libnotify example. It starts
``PrivateDBus`` and ``SpawnedMock``, sends a notification, inspects its contents
with ``GetMethodCalls("Notify")``, and simulates a user action with ``EmitSignal``.
Run it with ``python3 -m unittest tests.test_notification_daemon.TestNotificationActions``.
It requires PyGObject and the Notify introspection data (``python3-gi`` and
``gir1.2-notify-0.7`` on Debian/Ubuntu), in addition to dbus-daemon.

In your own test, replace notification creation with your application's code or
subprocess. ``GetMethodCalls("Notify")`` records the timestamps and arguments,
including application name, summary, body, actions, and hints.

The template does not display notifications or click buttons. Emit
``ActionInvoked`` with the ID returned to the client and the requested action key.
The client must process D-Bus signals: the example uses a GLib main loop with a
bounded wait, while a separate application uses its normal event loop.

Nested context managers stop the mock before the bus even when an assertion
fails. Run the example in its own process, since the private bus changes the
process's session-bus environment variable.
"""

# SPDX-License-Identifier: LGPL-3.0-or-later

__author__ = "Martin Pitt"
__copyright__ = """
(c) 2012 Canonical Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""

BUS_NAME = "org.freedesktop.Notifications"
MAIN_OBJ = "/org/freedesktop/Notifications"
MAIN_IFACE = "org.freedesktop.Notifications"
SYSTEM_BUS = False

# default capabilities, can be modified with "capabilities" parameter
default_caps = [
    "body",
    "body-markup",
    "icon-static",
    "image/svg+xml",
    "private-synchronous",
    "append",
    "private-icon-only",
    "truncation",
]


def load(mock, parameters):
    caps = parameters["capabilities"].split() if "capabilities" in parameters else default_caps

    # next notification ID
    mock.next_id = 1

    mock.AddMethods(
        MAIN_IFACE,
        [
            ("GetCapabilities", "", "as", f"ret = {caps!r}"),
            (
                "CloseNotification",
                "i",
                "",
                "if args[0] < self.next_id: self.EmitSignal('', 'NotificationClosed', 'uu', [args[0], 1])",
            ),
            ("GetServerInformation", "", "ssss", 'ret = ("mock-notify", "test vendor", "1.0", "1.1")'),
            (
                "Notify",
                "susssasa{sv}i",
                "u",
                """if args[1]:
    ret = args[1]
else:
    ret = self.next_id
    self.next_id += 1
""",
            ),
        ],
    )
