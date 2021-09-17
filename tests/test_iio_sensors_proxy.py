#!/usr/bin/python3
""" Tests for accounts service """

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Marco Trevisan'
__copyright__ = '(c) 2021 Canonical Ltd.'

import fcntl
import os
import shutil
import subprocess
import sys
import time
import unittest

import dbus
import dbus.mainloop.glib

from gi.repository import GLib
import dbusmock

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

have_monitor_sensor = shutil.which('monitor-sensor')


class TestIIOSensorsProxyBase(dbusmock.DBusTestCase):
    '''Test mocking iio-sensors-proxy'''
    dbus_interface = ''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_system_bus()
        cls.dbus_con = cls.get_dbus(True)

    def setUp(self):
        super().setUp()
        (self.p_mock, self.p_obj) = self.spawn_server_template(
            'iio-sensors-proxy', {}, stdout=subprocess.PIPE)

    def tearDown(self):
        if self.p_mock:
            self.p_mock.stdout.close()
            self.p_mock.terminate()
            self.p_mock.wait()

        super().tearDown()

    def get_property(self, name):
        return self.p_obj.Get(self.dbus_interface, name,
                              dbus_interface=dbus.PROPERTIES_IFACE)

    def get_internal_property(self, name):
        return self.p_obj.GetInternalProperty(name)

    def set_internal_property(self, name, value):
        return self.p_obj.SetInternalProperty(self.dbus_interface, name, value)

    def wait_for_properties_changed(self, max_wait=2000):
        changed_properties = []
        timeout_id = 0

        def on_properties_changed(interface, properties, _invalidated):
            nonlocal changed_properties

            if interface == self.dbus_interface:
                changed_properties = properties.keys()

        def on_timeout():
            nonlocal timeout_id

            timeout_id = 0

        loop = GLib.MainLoop()
        timeout_id = GLib.timeout_add(max_wait, on_timeout)
        match = self.p_obj.connect_to_signal('PropertiesChanged',
                                             on_properties_changed,
                                             dbus.PROPERTIES_IFACE)

        while not changed_properties and timeout_id != 0:
            loop.get_context().iteration(True)

        if timeout_id:
            GLib.source_remove(timeout_id)

        match.remove()

        return changed_properties

    def wait_for_property_changed(self, property_name, expected_value):
        self.assertIn(property_name, self.wait_for_properties_changed())
        self.assertEqual(
            self.get_internal_property(property_name), expected_value)


class TestIIOSensorsProxy(TestIIOSensorsProxyBase):
    ''' main SensorsProxy interface tests '''

    dbus_interface = 'net.hadess.SensorProxy'

    def test_accelerometer_none(self):
        self.assertFalse(self.get_property('HasAccelerometer'))

    def test_accelerometer_claimed(self):
        self.p_obj.ClaimAccelerometer()
        self.assertTrue(self.get_internal_property('AccelerometerOwners'))

    def test_accelerometer_claimed_released(self):
        self.p_obj.ClaimAccelerometer()
        self.assertTrue(self.get_internal_property('AccelerometerOwners'))
        self.p_obj.ReleaseAccelerometer()
        self.assertFalse(self.get_internal_property('AccelerometerOwners'))

    def test_accelerometer_available(self):
        self.assertFalse(self.get_property('HasAccelerometer'))
        self.set_internal_property('HasAccelerometer', True)
        self.assertTrue(self.get_property('HasAccelerometer'))

    def test_accelerometer_property_with_no_sensor(self):
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.set_internal_property('AccelerometerOrientation', 'normal')
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.DBus.Python.Exception')
        self.assertIn('Exception: No accelerometer sensor available',
                      ctx.exception.get_dbus_message().split('\n'))

    def test_accelerometer_claimed_properties_changes(self):
        self.set_internal_property('HasAccelerometer', True)
        self.p_obj.ClaimAccelerometer()
        self.set_internal_property('AccelerometerOrientation', 'normal')
        self.wait_for_property_changed('AccelerometerOrientation', 'normal')

    def test_accelerometer_unclaimed_properties_changes(self):
        self.set_internal_property('HasAccelerometer', True)
        self.assertTrue(self.get_property('HasAccelerometer'))
        self.set_internal_property('AccelerometerOrientation', 'normal')
        self.assertFalse(self.wait_for_properties_changed(max_wait=500))
        self.assertEqual(self.get_property('AccelerometerOrientation'),
                         'normal')

    def test_ambient_light_none(self):
        self.assertFalse(self.get_property('HasAmbientLight'))

    def test_ambient_light_claimed(self):
        self.p_obj.ClaimLight()
        self.assertTrue(self.get_internal_property('AmbientLightOwners'))
        self.assertFalse(self.get_property('HasAmbientLight'))

    def test_ambient_light_claimed_released(self):
        self.p_obj.ClaimLight()
        self.assertTrue(self.get_internal_property('AmbientLightOwners'))
        self.p_obj.ReleaseLight()
        self.assertFalse(self.get_internal_property('AmbientLightOwners'))

    def test_ambient_light_available(self):
        self.assertFalse(self.get_property('HasAmbientLight'))
        self.set_internal_property('HasAmbientLight', True)
        self.assertTrue(self.get_property('HasAmbientLight'))

    def test_ambient_light_property_with_no_sensor(self):
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.set_internal_property('LightLevelUnit', 'vendor')
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.DBus.Python.Exception')
        self.assertIn('Exception: No ambient_light sensor available',
                      ctx.exception.get_dbus_message().split('\n'))
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.set_internal_property('LightLevel', 0.5)
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.DBus.Python.Exception')
        self.assertIn('Exception: No ambient_light sensor available',
                      ctx.exception.get_dbus_message().split('\n'))

    def test_ambient_light_claimed_properties_changes(self):
        self.set_internal_property('HasAmbientLight', True)
        self.p_obj.ClaimLight()
        self.set_internal_property('LightLevelUnit', 'vendor')
        self.wait_for_property_changed('LightLevelUnit', 'vendor')
        self.set_internal_property('LightLevel', 111100.0)
        self.wait_for_property_changed('LightLevel', 111100.0)

    def test_ambient_light_unclaimed_properties_changes(self):
        self.set_internal_property('HasAmbientLight', True)
        self.assertTrue(self.get_property('HasAmbientLight'))
        self.set_internal_property('LightLevelUnit', 'vendor')
        self.assertFalse(self.wait_for_properties_changed(max_wait=500))
        self.assertEqual(self.get_property('LightLevelUnit'), 'vendor')

    def test_proximity_none(self):
        self.assertFalse(self.get_property('HasProximity'))

    def test_proximity_claimed(self):
        self.p_obj.ClaimProximity()
        self.assertTrue(self.get_internal_property('ProximityOwners'))
        self.assertFalse(self.get_property('HasProximity'))

    def test_proximity_claimed_released(self):
        self.p_obj.ClaimProximity()
        self.assertTrue(self.get_internal_property('ProximityOwners'))
        self.assertFalse(self.get_property('HasProximity'))
        self.p_obj.ReleaseProximity()
        self.assertFalse(self.get_internal_property('ProximityOwners'))

    def test_proximity_available(self):
        self.assertFalse(self.get_property('HasProximity'))
        self.set_internal_property('HasProximity', True)
        self.assertTrue(self.get_property('HasProximity'))

    def test_proximity_property_with_no_sensor(self):
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.set_internal_property('ProximityNear', True)
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.DBus.Python.Exception')
        self.assertIn('Exception: No proximity sensor available',
                      ctx.exception.get_dbus_message().split('\n'))

    def test_proximity_claimed_properties_changes(self):
        self.set_internal_property('HasProximity', True)
        self.p_obj.ClaimProximity()
        self.set_internal_property('ProximityNear', True)
        self.wait_for_property_changed('ProximityNear', True)

    def test_proximity_unclaimed_properties_changes(self):
        self.set_internal_property('HasProximity', True)
        self.assertTrue(self.get_property('HasProximity'))
        self.set_internal_property('ProximityNear', True)
        self.assertFalse(self.wait_for_properties_changed(max_wait=500))
        self.assertTrue(self.get_property('ProximityNear'))


class TestIIOSensorsProxyCompass(TestIIOSensorsProxyBase):
    ''' main SensorsProxy compass interface tests '''

    dbus_interface = 'net.hadess.SensorProxy.Compass'

    def test_compass_none(self):
        self.assertFalse(self.get_property('HasCompass'))

    def test_compass_claimed(self):
        self.p_obj.ClaimCompass()
        self.assertTrue(self.get_internal_property('CompassOwners'))
        self.assertFalse(self.get_property('HasCompass'))

    def test_compass_claimed_released(self):
        self.p_obj.ClaimCompass()
        self.assertTrue(self.get_internal_property('CompassOwners'))
        self.assertFalse(self.get_property('HasCompass'))
        self.p_obj.ReleaseCompass()
        self.assertFalse(self.get_internal_property('CompassOwners'))

    def test_compass_available(self):
        self.assertFalse(self.get_property('HasCompass'))
        self.set_internal_property('HasCompass', True)
        self.assertTrue(self.get_property('HasCompass'))

    def test_compass_property_with_no_sensor(self):
        with self.assertRaises(dbus.exceptions.DBusException) as ctx:
            self.set_internal_property('CompassHeading', 180)
        self.assertEqual(ctx.exception.get_dbus_name(),
                         'org.freedesktop.DBus.Python.Exception')
        self.assertIn('Exception: No compass sensor available',
                      ctx.exception.get_dbus_message().split('\n'))

    def test_compass_claimed_properties_changes(self):
        self.set_internal_property('HasCompass', True)
        self.p_obj.ClaimCompass()
        self.set_internal_property('CompassHeading', 55)
        self.wait_for_property_changed('CompassHeading', 55)

    def test_compass_unclaimed_properties_changes(self):
        self.set_internal_property('HasCompass', True)
        self.assertTrue(self.get_property('HasCompass'))
        self.set_internal_property('CompassHeading', 85)
        self.assertFalse(self.wait_for_properties_changed(max_wait=500))
        self.assertEqual(self.get_property('CompassHeading'), 85)


@unittest.skipUnless(have_monitor_sensor,
                     'monitor-sensor utility not available')
class TestIIOSensorsProxyMonitorSensorBase(TestIIOSensorsProxyBase):
    ''' Base SensorsProxy interface tests using monitor-sensor'''

    p_monitor_sensor = None

    def start_monitor_sensor(self):
        self.assertIsNone(self.p_monitor_sensor)
        # pylint: disable=consider-using-with
        self.p_monitor_sensor = subprocess.Popen(
            'monitor-sensor', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        flags = fcntl.fcntl(self.p_monitor_sensor.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.p_monitor_sensor.stdout, fcntl.F_SETFL,
                    flags | os.O_NONBLOCK)
        self.assertOutputContains([
            '    Waiting for iio-sensor-proxy to appear',
            '+++ iio-sensor-proxy appeared',
        ])

    def stop_monitor_sensor(self):
        self.assertIsNotNone(self.p_monitor_sensor)
        self.assertEmptyOutput()
        self.p_monitor_sensor.stdout.close()
        self.p_monitor_sensor.terminate()
        self.p_monitor_sensor.wait()

    def tearDown(self):
        if self.p_monitor_sensor:
            self.stop_monitor_sensor()
        super().tearDown()

    def assertOutputContains(self, expected_lines, max_wait=2000):
        self.assertIsNotNone(self.p_monitor_sensor)
        start_time = int(time.time() * 1000)
        for line in expected_lines:
            output = None
            while True:
                output = self.p_monitor_sensor.stdout.readline()
                if output:
                    break
                self.assertLessEqual(int(time.time() * 1000) - start_time,
                                     max_wait, msg='Timeout exceeded')
            self.assertEqual(output.decode('utf-8'), f'{line}\n')

    def assertOutputEquals(self, expected_lines, max_wait=2000):
        self.assertOutputContains(expected_lines, max_wait)
        self.assertEmptyOutput()

    def assertEmptyOutput(self, max_wait=100):
        start_time = int(time.time() * 1000)
        while int(time.time() * 1000) - start_time < max_wait:
            self.assertFalse(self.p_monitor_sensor.stdout.readline(),
                             msg='Unexpected output')


class TestIIOSensorsProxyMonitorSensor(TestIIOSensorsProxyMonitorSensorBase):
    ''' main SensorsProxy interface tests using monitor-sensor'''

    dbus_interface = 'net.hadess.SensorProxy'

    def test_accelerometer_added(self):
        self.set_internal_property('HasAccelerometer', True)
        self.start_monitor_sensor()

        self.assertOutputEquals([
            '=== Has accelerometer (orientation: undefined)',
            '=== No ambient light sensor',
            '=== No proximity sensor',
        ])

    def test_accelerometer_changes(self):
        self.test_accelerometer_added()
        self.set_internal_property('AccelerometerOrientation', 'normal')
        self.set_internal_property('AccelerometerOrientation', 'left-up')
        self.set_internal_property('AccelerometerOrientation', 'bottom-up')
        self.assertOutputEquals([
            '    Accelerometer orientation changed: normal',
            '    Accelerometer orientation changed: left-up',
            '    Accelerometer orientation changed: bottom-up',
        ])

    def test_ambient_light_added(self):
        self.set_internal_property('HasAmbientLight', True)
        self.start_monitor_sensor()

        self.assertOutputEquals([
            '=== No accelerometer',
            '=== Has ambient light sensor (value: 0.000000, unit: lux)',
            '=== No proximity sensor',
        ])

    def test_ambient_light_changes(self):
        self.test_ambient_light_added()
        self.set_internal_property('LightLevelUnit', 'vendor')
        self.set_internal_property('LightLevel', 0.3)
        self.set_internal_property('LightLevel', 0.5)
        self.set_internal_property('LightLevelUnit', 'lux')
        self.set_internal_property('LightLevel', 111100.0)

        self.assertOutputEquals([
            '    Light changed: 0.300000 (vendor)',
            '    Light changed: 0.500000 (vendor)',
            '    Light changed: 111100.000000 (lux)',
        ])

    def test_proximity_sensor_added(self):
        self.set_internal_property('HasProximity', True)
        self.start_monitor_sensor()

        self.assertOutputEquals([
            '=== No accelerometer',
            '=== No ambient light sensor',
            '=== Has proximity sensor (near: 0)',
        ])

    def test_proximity_sensor_changes(self):
        self.test_proximity_sensor_added()

        self.set_internal_property('ProximityNear', True)
        self.set_internal_property('ProximityNear', False)

        self.assertOutputEquals([
            '    Proximity value changed: 1',
            '    Proximity value changed: 0',
        ])


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(
        stream=sys.stdout))
