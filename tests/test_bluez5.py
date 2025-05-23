# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = "Philip Withnall"
__copyright__ = """
(c) 2013 Collabora Ltd.
(c) 2017 - 2022 Martin Pitt <martin@piware.de>
"""


import os
import re
import shutil
import subprocess
import sys
import time
import tracemalloc
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import dbus
import dbus.mainloop.glib
from gi.repository import GLib
from packaging.version import Version

import dbusmock

tracemalloc.start(25)
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

have_bluetoothctl = shutil.which("bluetoothctl")
have_pbap_client = shutil.which("pbap-client")

os_release = Path("/etc/os-release")
el10 = os_release.exists() and "platform:el10" in os_release.read_text("UTF-8")


def _run_bluetoothctl(command):
    """Run bluetoothctl with the given command.

    Return its output as a list of lines, with the command prompt removed
    from each, and empty lines eliminated.

    If bluetoothctl returns a non-zero exit code, raise an Exception.
    """
    with subprocess.Popen(
        ["bluetoothctl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True
    ) as process:
        time.sleep(0.5)  # give it time to query the bus
        out, err = process.communicate(input="list\n" + command + "\nquit\n")

        # Ignore output on stderr unless bluetoothctl dies.
        if process.returncode != 0:
            raise dbus.exceptions.DBusException(
                f'bluetoothctl died with status {process.returncode} and errors: {err or ""}',
                name="org.freedesktop.DBus.Mock.Error",
            )

    # Strip the prompt and escape sequences from the start of every line,
    # then remove empty lines.
    #
    # The prompt looks like `[bluetooth]# `, potentially containing command
    # line colour control codes.
    def remove_prefix(line):
        line = re.sub(r"\x1b\[[0-9;]*[mPK]", "", line)
        line = re.sub(r"^\[bluetooth\]# ", "", line)
        return line.strip()

    lines = out.split("\n")
    lines = map(remove_prefix, lines)
    lines = filter(lambda line: line != "", lines)

    # Filter out the echoed commands. (bluetoothctl uses readline.)
    return list(filter(lambda line: line not in ["list", command, "quit"], lines))


def _introspect_property_types(obj, interface):
    dbus_introspect = dbus.Interface(obj, dbus.INTROSPECTABLE_IFACE)
    xml = dbus_introspect.Introspect()
    root = ET.fromstring(xml)

    prop_types = {}
    for prop in root.findall(f'./interface[@name="{interface}"]/property'):
        name, type_sig = prop.attrib["name"], prop.attrib["type"]
        prop_types[name] = type_sig
    return prop_types


@unittest.skipUnless(have_bluetoothctl, "bluetoothctl not installed")
class TestBlueZ5(dbusmock.DBusTestCase):
    """Test mocking bluetoothd"""

    @classmethod
    def setUpClass(cls):
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)
        (cls.p_mock, cls.obj_bluez) = cls.spawn_server_template("bluez5", {}, stdout=subprocess.PIPE)

        out = _run_bluetoothctl("version")
        version = next(line.split(" ")[-1] for line in out if line.startswith("Version"))
        cls.bluez5_version = Version(version)

    def setUp(self):
        self.obj_bluez.Reset()
        self.dbusmock = dbus.Interface(self.obj_bluez, dbusmock.MOCK_IFACE)
        self.dbusmock_bluez = dbus.Interface(self.obj_bluez, "org.bluez.Mock")

    def test_no_adapters(self):
        # Check for adapters.
        out = _run_bluetoothctl("list")
        for line in out:
            self.assertFalse(line.startswith("Controller "))

    def test_one_adapter(self):
        # Chosen parameters.
        adapter_name = "hci0"
        system_name = "my-computer"

        # Add an adapter
        path = self.dbusmock_bluez.AddAdapter(adapter_name, system_name)
        self.assertEqual(path, "/org/bluez/" + adapter_name)

        adapter = self.dbus_con.get_object("org.bluez", path)
        address = adapter.Get("org.bluez.Adapter1", "Address")
        address_type = adapter.Get("org.bluez.Adapter1", "AddressType")

        # Check for the adapter.
        out = _run_bluetoothctl("list")
        self.assertIn("Controller " + address + " " + system_name + " [default]", out)

        out = _run_bluetoothctl("show " + address)
        if address_type is not None:
            self.assertIn(f"Controller {address} ({address_type})", out)
        else:
            self.assertIn("Controller " + address, out)
        self.assertIn("Name: " + system_name, out)
        self.assertIn("Alias: " + system_name, out)
        self.assertIn("Powered: yes", out)
        self.assertIn("Discoverable: no", out)
        self.assertIn("Pairable: yes", out)
        self.assertIn("Discovering: no", out)
        self.assertIn("Roles: central", out)
        self.assertIn("Roles: peripheral", out)

        # Advertising Manager
        self.assertIn("Advertising Features:", out)
        self.assertIn("ActiveInstances: 0x00 (0)", out)
        self.assertIn("SupportedInstances: 0x05 (5)", out)
        self.assertIn("SupportedIncludes: tx-power", out)
        self.assertIn("SupportedIncludes: appearance", out)
        self.assertIn("SupportedIncludes: local-name", out)
        self.assertIn("SupportedSecondaryChannels: 1M", out)
        self.assertIn("SupportedSecondaryChannels: 2M", out)

        # SupportedFeatures was added to the API with BlueZ 5.57
        if self.bluez5_version >= Version("5.57"):
            self.assertIn("SupportedFeatures: CanSetTxPower", out)
            self.assertIn("SupportedFeatures: HardwareOffload", out)

        # Capabilities key-value format was changed in BlueZ 5.70
        if self.bluez5_version <= Version("5.70"):
            capabilities = [
                ["SupportedCapabilities Key: MinTxPower", "SupportedCapabilities Value: -34"],
                ["SupportedCapabilities Key: MaxTxPower", "SupportedCapabilities Value: 7"],
                ["SupportedCapabilities Key: MaxAdvLen", "SupportedCapabilities Value: 0xfb (251)"],
                ["SupportedCapabilities Key: MaxScnRspLen", "SupportedCapabilities Value: 0xfb (251)"],
            ]
            for capability in capabilities:
                self.assertTrue(all(cap in out for cap in capability), f"Expected ${capability} in: ${out}")
        else:
            self.assertIn("SupportedCapabilities.MinTxPower: 0xffffffde (-34)", out)
            self.assertIn("SupportedCapabilities.MaxTxPower: 0x0007 (7)", out)
            self.assertIn("SupportedCapabilities.MaxAdvLen: 0xfb (251)", out)
            self.assertIn("SupportedCapabilities.MaxScnRspLen: 0xfb (251)", out)

        # Advertisement Monitor
        self.assertIn("Advertisement Monitor Features:", out)
        self.assertIn("SupportedMonitorTypes: or_patterns", out)

    def test_adapter_property_types(self):
        adapter_name = "hci0"
        system_name = "my-computer"

        path = self.dbusmock_bluez.AddAdapter(adapter_name, system_name)
        self.assertEqual(path, "/org/bluez/" + adapter_name)

        # Test that the property types on the interfaces are defined correctly
        adapter = self.dbus_con.get_object("org.bluez", path)

        adapter_prop_types = _introspect_property_types(adapter, "org.bluez.Adapter1")
        self.assertEqual(
            adapter_prop_types,
            {
                "Address": "s",
                "AddressType": "s",
                "Alias": "s",
                "Class": "u",
                "Discoverable": "b",
                "DiscoverableTimeout": "u",
                "Discovering": "b",
                "Modalias": "s",
                "Name": "s",
                "Pairable": "b",
                "PairableTimeout": "u",
                "Powered": "b",
                "Roles": "as",
                "UUIDs": "as",
            },
        )

        adv_manager_prop_types = _introspect_property_types(adapter, "org.bluez.LEAdvertisingManager1")
        self.assertEqual(
            adv_manager_prop_types,
            {
                "ActiveInstances": "y",
                "SupportedCapabilities": "a{sv}",
                "SupportedFeatures": "as",
                "SupportedIncludes": "as",
                "SupportedInstances": "y",
                "SupportedSecondaryChannels": "as",
            },
        )

        adv_monitor_manager_prop_types = _introspect_property_types(adapter, "org.bluez.AdvertisementMonitorManager1")
        self.assertEqual(
            adv_monitor_manager_prop_types,
            {
                "SupportedMonitorTypes": "as",
            },
        )

    def test_no_devices(self):
        # Add an adapter.
        adapter_name = "hci0"
        path = self.dbusmock_bluez.AddAdapter(adapter_name, "my-computer")
        self.assertEqual(path, "/org/bluez/" + adapter_name)

        # Check for devices.
        out = _run_bluetoothctl("devices")
        self.assertIn("Controller 00:01:02:03:04:05 my-computer [default]", out)

    def test_one_device(self):
        # Add an adapter.
        adapter_name = "hci0"
        path = self.dbusmock_bluez.AddAdapter(adapter_name, "my-computer")
        self.assertEqual(path, "/org/bluez/" + adapter_name)

        # Add a device.
        address = "11:22:33:44:55:66"
        alias = "My Phone"

        path = self.dbusmock_bluez.AddDevice(adapter_name, address, alias)
        self.assertEqual(path, "/org/bluez/" + adapter_name + "/dev_" + address.replace(":", "_"))

        # Check for the device.
        out = _run_bluetoothctl("devices")
        self.assertIn("Device " + address + " " + alias, out)

        # Check the device's properties.
        out = "\n".join(_run_bluetoothctl("info " + address))
        self.assertIn("Device " + address, out)
        self.assertIn("Name: " + alias, out)
        self.assertIn("Alias: " + alias, out)
        self.assertIn("Paired: no", out)
        self.assertIn("Trusted: no", out)
        self.assertIn("Blocked: no", out)
        self.assertIn("Connected: no", out)

    def test_pairing_device(self):
        # Add an adapter.
        adapter_name = "hci0"
        path = self.dbusmock_bluez.AddAdapter(adapter_name, "my-computer")
        self.assertEqual(path, "/org/bluez/" + adapter_name)

        # Add a device.
        address = "11:22:33:44:55:66"
        alias = "My Phone"

        path = self.dbusmock_bluez.AddDevice(adapter_name, address, alias)
        self.assertEqual(path, "/org/bluez/" + adapter_name + "/dev_" + address.replace(":", "_"))

        # Pair with the device.
        self.dbusmock_bluez.PairDevice(adapter_name, address)

        # Check the device's properties.
        out = "\n".join(_run_bluetoothctl("info " + address))
        self.assertIn("Device " + address, out)
        self.assertIn("Paired: yes", out)

    def test_add_advertisement(self):
        # When an advertisement is added
        adv_path = self.dbusmock_bluez.AddAdvertisement("bc001")
        # Then the path is returned
        self.assertEqual(adv_path, "/org/dbusmock/bluez/advertisement/bc001")
        # And the object is exported on the bus
        adv = self.dbus_con.get_object("org.bluez", adv_path)
        adv_type = adv.Get("org.bluez.LEAdvertisement1", "Type", dbus_interface=dbus.PROPERTIES_IFACE)
        # And has the correct properties
        self.assertEqual(adv_type, "broadcast")

    def test_register_advertisement(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")
        props = dbus.Interface(adapter, dbus.PROPERTIES_IFACE)
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")

        # And no active instances
        self.assertEqual(active_instances, 0)
        self.assertEqual(supported_instances, 5)

        # When an advertisement is registered
        # Then no error is raised
        adv_manager.RegisterAdvertisement("/adv0", {})

        # And active instances is incremented
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        self.assertEqual(active_instances, 1)
        # And supported instances is decremented
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")
        self.assertEqual(supported_instances, 4)

    def test_register_advertisement_duplicate(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")
        props = dbus.Interface(adapter, dbus.PROPERTIES_IFACE)

        # When an advertisement is registered twice
        adv_manager.RegisterAdvertisement("/adv0", {})

        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, "Already registered") as ctx:
            adv_manager.RegisterAdvertisement("/adv0", {})
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.AlreadyExists")

        # And active instances is not incremented
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        self.assertEqual(active_instances, 1)
        # And supported instances is not decremented
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")
        self.assertEqual(supported_instances, 4)

    def test_register_advertisement_max_instances(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")
        props = dbus.Interface(adapter, dbus.PROPERTIES_IFACE)
        max_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")

        # When more advertisements are registered than supported
        for i in range(max_instances):
            adv_manager.RegisterAdvertisement(f"/adv{i}", {})

        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, "Maximum number of advertisements reached") as ctx:
            adv_manager.RegisterAdvertisement(f"/adv{int(max_instances)}", {})
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.NotPermitted")

        # And active instances is equal to the number of supported instances
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        self.assertEqual(active_instances, max_instances)
        # And supported instances is now zero
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")
        self.assertEqual(supported_instances, 0)

    def test_unregister_advertisement(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")
        props = dbus.Interface(adapter, dbus.PROPERTIES_IFACE)

        # And a registered advertisement
        adv_manager.RegisterAdvertisement("/adv0", {})
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")
        self.assertEqual(active_instances, 1)
        self.assertEqual(supported_instances, 4)

        # When the advertisement is unregistered
        # Then no error is raised
        adv_manager.UnregisterAdvertisement("/adv0")
        # And active instances is decremented
        active_instances = props.Get(adv_manager.dbus_interface, "ActiveInstances")
        self.assertEqual(active_instances, 0)
        # And supported instances is incremented
        supported_instances = props.Get(adv_manager.dbus_interface, "SupportedInstances")
        self.assertEqual(supported_instances, 5)

    def test_unregister_advertisement_unknown(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_manager = dbus.Interface(adapter, "org.bluez.LEAdvertisingManager1")

        # When an advertisement is unregistered without registering it first
        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, "Unknown advertisement") as ctx:
            adv_manager.UnregisterAdvertisement("/adv0")
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.DoesNotExist")

    def test_add_monitor(self):
        # When an advertisement monitor is added
        adv_path = self.dbusmock_bluez.AddMonitor("mon001")
        # Then the path is returned
        self.assertEqual(adv_path, "/org/dbusmock/bluez/monitor/mon001")
        # And the object is exported on the bus
        adv = self.dbus_con.get_object("org.bluez", adv_path)
        adv_type = adv.Get("org.bluez.AdvertisementMonitor1", "Type", dbus_interface=dbus.PROPERTIES_IFACE)
        # And has the correct properties
        self.assertEqual(adv_type, "or_patterns")

    def test_register_monitor(self):
        # Given an adapter with the AdvertisementMonitorManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_monitor_manager = dbus.Interface(adapter, "org.bluez.AdvertisementMonitorManager1")

        # When an advertisement monitor is registered
        # Then no error is raised
        adv_monitor_manager.RegisterMonitor("/monitor0")

    def test_register_monitor_duplicate(self):
        # Given an adapter with the AdvertisementMonitorManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_monitor_manager = dbus.Interface(adapter, "org.bluez.AdvertisementMonitorManager1")

        # When an advertisement monitor is registered twice
        adv_monitor_manager.RegisterMonitor("/monitor0")

        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, "Already registered") as ctx:
            adv_monitor_manager.RegisterMonitor("/monitor0")
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.AlreadyExists")

    def test_unregister_monitor(self):
        # Given an adapter with the AdvertisementMonitorManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_monitor_manager = dbus.Interface(adapter, "org.bluez.AdvertisementMonitorManager1")

        # And a registered advertisement monitor
        adv_monitor_manager.RegisterMonitor("/monitor0")
        # When the advertisement monitor is unregistered
        # Then no error is raised
        adv_monitor_manager.UnregisterMonitor("/monitor0")

    def test_unregister_monitor_unknown(self):
        # Given an adapter with the AdvertisementMonitorManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)
        adv_monitor_manager = dbus.Interface(adapter, "org.bluez.AdvertisementMonitorManager1")

        # When an advertisement monitor is unregistered without registering it first
        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, "Unknown monitor") as ctx:
            adv_monitor_manager.UnregisterMonitor("/monitor0")
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.DoesNotExist")

    @unittest.skipIf(el10, "https://issues.redhat.com/browse/RHEL-56021")
    def test_advertise(self):
        # Given an adapter with the LEAdvertisingManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)

        # When an advertisement is started via bluetoothctl
        _run_bluetoothctl("advertise broadcast")

        # Then the RegisterAdvertisement method was called
        mock_calls = adapter.GetMethodCalls("RegisterAdvertisement", dbus_interface="org.freedesktop.DBus.Mock")
        self.assertEqual(len(mock_calls), 1)
        path, *_ = mock_calls[0][1]
        self.assertEqual(path, "/org/bluez/advertising")

    def test_monitor(self):
        # Given an adapter with the AdvertisementMonitorManager1 interface
        path = self.dbusmock_bluez.AddAdapter("hci0", "my-computer")
        adapter = self.dbus_con.get_object("org.bluez", path)

        # When an advertisement monitor is configured via bluetoothctl
        out = _run_bluetoothctl("monitor.add-or-pattern 0 255 01")

        # Then bluetoothctl reports success
        self.assertIn("Advertisement Monitor 0 added", out)

        # And the RegisterMonitor method was called
        mock_calls = adapter.GetMethodCalls("RegisterMonitor", dbus_interface="org.freedesktop.DBus.Mock")
        self.assertEqual(len(mock_calls), 1)
        path, *_ = mock_calls[0][1]
        self.assertEqual(path, "/")

    def test_register_agent(self):
        # Given BlueZ with the AgentManager1 interface
        bluez = self.dbus_con.get_object("org.bluez", "/org/bluez")
        agent_manager = dbus.Interface(bluez, "org.bluez.AgentManager1")
        agent_path = "/org/dbusmock/bluezagent"

        # When an agent with the default capabiities is registered
        # Then no error is raised
        agent_manager.RegisterAgent(agent_path, "")

    def test_register_agent_duplicate(self):
        # Given BlueZ with the AgentManager1 interface
        bluez = self.dbus_con.get_object("org.bluez", "/org/bluez")
        agent_manager = dbus.Interface(bluez, "org.bluez.AgentManager1")
        agent_path = "/org/dbusmock/bluezagent"

        # When an agent is registered twice
        agent_manager.RegisterAgent(agent_path, "")

        # Then an error is raised
        with self.assertRaisesRegex(
            dbus.exceptions.DBusException, f"Another agent is already registered {agent_path}"
        ) as ctx:
            agent_manager.RegisterAgent(agent_path, "")
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.AlreadyExists")

    def test_unregister_agent(self):
        # Given BlueZ with the AgentManager1 interface
        bluez = self.dbus_con.get_object("org.bluez", "/org/bluez")
        agent_manager = dbus.Interface(bluez, "org.bluez.AgentManager1")
        agent_path = "/org/dbusmock/bluezagent"

        # And a registered agent
        agent_manager.RegisterAgent(agent_path, "")
        # When the agent is unregistered
        # Then no error is raised
        agent_manager.UnregisterAgent(agent_path)

    def test_unregister_agent_unknown(self):
        # Given BlueZ with the AgentManager1 interface
        bluez = self.dbus_con.get_object("org.bluez", "/org/bluez")
        agent_manager = dbus.Interface(bluez, "org.bluez.AgentManager1")
        agent_path = "/org/dbusmock/bluezagent"

        # When an agent is unregistered without registering it first
        # Then an error is raised
        with self.assertRaisesRegex(dbus.exceptions.DBusException, f"Agent not registered {agent_path}") as ctx:
            agent_manager.UnregisterAgent(agent_path)
        self.assertEqual(ctx.exception.get_dbus_name(), "org.bluez.Error.DoesNotExist")

    def test_agent(self):
        # Given BlueZ with the AgentManager1 interface
        bluez = self.dbus_con.get_object("org.bluez", "/org/bluez")

        # When bluetoothctl is started
        out = _run_bluetoothctl("list")

        # Then it reports that the agent was registered
        if self.bluez5_version >= Version("5.57"):
            self.assertIn("Agent registered", out)

        # And the RegisterAgent method was called
        mock_calls = bluez.GetMethodCalls("RegisterAgent", dbus_interface="org.freedesktop.DBus.Mock")
        self.assertEqual(len(mock_calls), 1)
        path, capabilities = mock_calls[0][1]
        self.assertEqual(path, "/org/bluez/agent")
        self.assertEqual(capabilities, "")


@unittest.skipUnless(have_pbap_client, "pbap-client not installed (copy it from bluez/test)")
class TestBlueZObex(dbusmock.DBusTestCase):
    """Test mocking obexd"""

    @classmethod
    def setUpClass(cls):
        cls.start_session_bus()
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        # bluetoothd
        (self.p_mock, self.obj_bluez) = self.spawn_server_template("bluez5", {}, stdout=subprocess.PIPE)
        self.dbusmock_bluez = dbus.Interface(self.obj_bluez, "org.bluez.Mock")

        # obexd
        (self.p_mock_obex, self.obj_obex) = self.spawn_server_template("bluez5-obex", {}, stdout=subprocess.PIPE)
        self.dbusmock = dbus.Interface(self.obj_obex, dbusmock.MOCK_IFACE)
        self.dbusmock_obex = dbus.Interface(self.obj_obex, "org.bluez.obex.Mock")

    def tearDown(self):
        self.p_mock.stdout.close()
        self.p_mock.terminate()
        self.p_mock.wait()

        self.p_mock_obex.stdout.close()
        self.p_mock_obex.terminate()
        self.p_mock_obex.wait()

    def test_everything(self):
        # Set up an adapter and device.
        adapter_name = "hci0"
        device_address = "11:22:33:44:55:66"
        device_alias = "My Phone"

        ml = GLib.MainLoop()

        self.dbusmock_bluez.AddAdapter(adapter_name, "my-computer")
        self.dbusmock_bluez.AddDevice(adapter_name, device_address, device_alias)
        self.dbusmock_bluez.PairDevice(adapter_name, device_address)

        transferred_files = []

        def _transfer_created_cb(path, params, transfer_filename):
            bus = self.get_dbus(False)
            obj = bus.get_object("org.bluez.obex", path)
            transfer = dbus.Interface(obj, "org.bluez.obex.transfer1.Mock")

            Path(transfer_filename).write_bytes(
                b"BEGIN:VCARD\r\n"
                b"VERSION:3.0\r\n"
                b"FN:Forrest Gump\r\n"
                b"TEL;TYPE=WORK,VOICE:(111) 555-1212\r\n"
                b"TEL;TYPE=HOME,VOICE:(404) 555-1212\r\n"
                b"EMAIL;TYPE=PREF,INTERNET:forrestgump@example.com\r\n"
                b"EMAIL:test@example.com\r\n"
                b"URL;TYPE=HOME:http://example.com/\r\n"
                b"URL:http://forest.com/\r\n"
                b"URL:https://test.com/\r\n"
                b"END:VCARD\r\n"
            )

            transfer.UpdateStatus(True)
            transferred_files.append(transfer_filename)

        self.dbusmock_obex.connect_to_signal("TransferCreated", _transfer_created_cb)

        # Run pbap-client, then run the GLib main loop. The main loop will quit
        # after a timeout, at which point the code handles output from
        # pbap-client and waits for it to terminate. Integrating
        # process.communicate() with the GLib main loop to avoid the timeout is
        # too difficult.
        with subprocess.Popen(
            ["pbap-client", device_address], stdout=subprocess.PIPE, stderr=sys.stderr, universal_newlines=True
        ) as process:
            GLib.timeout_add(5000, ml.quit)
            ml.run()

            out = process.communicate()[0]

        lines = out.split("\n")
        lines = filter(lambda line: line != "", lines)
        lines = list(lines)

        # Clean up the transferred files.
        for f in transferred_files:
            try:
                os.remove(f)
            except OSError:
                pass

        # See what pbap-client sees.
        self.assertIn("Creating Session", lines)
        self.assertIn("--- Select Phonebook PB ---", lines)
        self.assertIn("--- GetSize ---", lines)
        self.assertIn("Size = 0", lines)
        self.assertIn("--- List vCard ---", lines)
        self.assertIn("Transfer /org/bluez/obex/client/session0/transfer0 complete", lines)
        self.assertIn("Transfer /org/bluez/obex/client/session0/transfer1 complete", lines)
        self.assertIn("Transfer /org/bluez/obex/client/session0/transfer2 complete", lines)
        self.assertIn("Transfer /org/bluez/obex/client/session0/transfer3 complete", lines)
        self.assertIn("FINISHED", lines)

        self.assertNotIn("ERROR", lines)


if __name__ == "__main__":
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
