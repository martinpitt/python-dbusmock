"""notification-daemon mock template

This creates the expected methods and properties of the notification-daemon
services, but no devices. You can specify non-default capabilities in
"parameters".
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
