#!/usr/bin/python3

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Martin Pitt'
__email__ = 'martin.pitt@ubuntu.com'
__copyright__ = '(c) 2013 Canonical Ltd.'
__license__ = 'LGPL 3+'

import unittest
import sys
import subprocess
import os

import dbus
import dbusmock

script_dir = os.environ.get('OFONO_SCRIPT_DIR', '/usr/share/ofono/scripts')

have_scripts = os.access(os.path.join(script_dir, 'list-modems'), os.X_OK)


@unittest.skipUnless(have_scripts,
                     'ofono scripts not available, set $OFONO_SCRIPT_DIR')
class TestOfono(dbusmock.DBusTestCase):
    '''Test mocking ofonod'''

    @classmethod
    def setUpClass(klass):
        klass.start_system_bus()
        klass.dbus_con = klass.get_dbus(True)
        (klass.p_mock, klass.obj_ofono) = klass.spawn_server_template(
            'ofono', {}, stdout=subprocess.PIPE)

    def setUp(self):
        self.obj_ofono.Reset()

    def test_list_modems(self):
        '''Manager.GetModems()'''

        out = subprocess.check_output([os.path.join(script_dir, 'list-modems')])
        self.assertTrue(out.startswith(b'[ /ril_0 ]'), out)
        self.assertIn(b'Powered = 1', out)
        self.assertIn(b'Online = 1', out)
        self.assertIn(b'Model = Mock Modem', out)
        self.assertIn(b'[ org.ofono.NetworkRegistration ]', out)
        self.assertIn(b'Status = registered', out)
        self.assertIn(b'Name = fake.tel', out)
        self.assertIn(b'Technology = gsm', out)
        self.assertIn(b'[ org.ofono.SimManager ]', out)
        self.assertIn(b'PinRequired = none', out)
        self.assertIn(b'Present = 1', out)
        self.assertIn(b'CardIdentifier = 893581234000000000000', out)
        self.assertIn(b'MobileCountryCode = 310', out)
        self.assertIn(b'MobileNetworkCode = 150', out)
        self.assertIn(b'Serial = 12345678-1234-1234-1234-000000000000', out)
        self.assertIn(b'SubscriberIdentity = 310150000000000', out)

    def test_outgoing_call(self):
        '''outgoing voice call'''

        # no calls by default
        out = subprocess.check_output([os.path.join(script_dir, 'list-calls')])
        self.assertEqual(out, b'[ /ril_0 ]\n')

        # start call
        out = subprocess.check_output([os.path.join(script_dir, 'dial-number'), '12345'])
        self.assertEqual(out, b'Using modem /ril_0\n/ril_0/voicecall01\n')

        out = subprocess.check_output([os.path.join(script_dir, 'list-calls')])
        self.assertIn(b'/ril_0/voicecall01', out)
        self.assertIn(b'LineIdentification = 12345', out)
        self.assertIn(b'State = dialing', out)

        out = subprocess.check_output([os.path.join(script_dir, 'hangup-call'),
                                      '/ril_0/voicecall01'])
        self.assertEqual(out, b'')

        # no active calls any more
        out = subprocess.check_output([os.path.join(script_dir, 'list-calls')])
        self.assertEqual(out, b'[ /ril_0 ]\n')

    def test_hangup_all(self):
        '''multiple outgoing voice calls'''

        out = subprocess.check_output([os.path.join(script_dir, 'dial-number'), '12345'])
        self.assertEqual(out, b'Using modem /ril_0\n/ril_0/voicecall01\n')

        out = subprocess.check_output([os.path.join(script_dir, 'dial-number'), '54321'])
        self.assertEqual(out, b'Using modem /ril_0\n/ril_0/voicecall02\n')

        out = subprocess.check_output([os.path.join(script_dir, 'list-calls')])
        self.assertIn(b'/ril_0/voicecall01', out)
        self.assertIn(b'/ril_0/voicecall02', out)
        self.assertIn(b'LineIdentification = 12345', out)
        self.assertIn(b'LineIdentification = 54321', out)

        out = subprocess.check_output([os.path.join(script_dir, 'hangup-all')])
        out = subprocess.check_output([os.path.join(script_dir, 'list-calls')])
        self.assertEqual(out, b'[ /ril_0 ]\n')

    def test_list_operators(self):
        '''list operators'''

        out = subprocess.check_output([os.path.join(script_dir, 'list-operators')],
                                      universal_newlines=True)
        self.assertTrue(out.startswith('[ /ril_0 ]'), out)
        self.assertIn('[ /ril_0/operator/op1 ]', out)
        self.assertIn('Status = current', out)
        self.assertIn('Technologies = gsm', out)
        self.assertIn('MobileNetworkCode = 11', out)
        self.assertIn('MobileCountryCode = 777', out)
        self.assertIn('Name = fake.tel', out)

    def test_get_operators_for_two_modems(self):
        '''Add second modem, list operators on both'''

        iface = 'org.ofono.NetworkRegistration'

        # add second modem
        self.obj_ofono.AddModem('sim2', {'Powered': True})

        # get modem proxy, get netreg interface
        modem_0 = self.dbus_con.get_object('org.ofono', '/ril_0')
        modem_0_netreg = dbus.Interface(
            modem_0, dbus_interface=iface)
        modem_0_ops = modem_0_netreg.GetOperators()

        # get modem proxy, get netreg interface
        modem_1 = self.dbus_con.get_object('org.ofono', '/sim2')
        modem_1_netreg = dbus.Interface(
            modem_1, dbus_interface=iface)
        modem_1_ops = modem_1_netreg.GetOperators()

        self.assertIn('/ril_0/operator/op1', str(modem_0_ops))
        self.assertNotIn('/sim2', str(modem_0_ops))

        self.assertIn('/sim2/operator/op1', str(modem_1_ops))
        self.assertNotIn('/ril_0', str(modem_1_ops))

    def test_second_modem(self):
        '''Add a second modem'''
        out = subprocess.check_output([os.path.join(script_dir, 'list-modems')])
        self.assertIn(b'CardIdentifier = 893581234000000000000', out)
        self.assertIn(b'Serial = 12345678-1234-1234-1234-000000000000', out)
        self.assertIn(b'SubscriberIdentity = 310150000000000', out)

        self.obj_ofono.AddModem('sim2', {'Powered': True})

        out = subprocess.check_output([os.path.join(script_dir, 'list-modems')])
        self.assertTrue(out.startswith(b'[ /ril_0 ]'), out)
        self.assertIn(b'[ /sim2 ]', out)
        self.assertIn(b'Powered = 1', out)
        self.assertIn(b'CardIdentifier = 893581234000000000000', out)
        self.assertIn(b'Serial = 12345678-1234-1234-1234-000000000000', out)
        self.assertIn(b'SubscriberIdentity = 310150000000000', out)
        self.assertIn(b'CardIdentifier = 893581234000000000001', out)
        self.assertIn(b'Serial = 12345678-1234-1234-1234-000000000001', out)
        self.assertIn(b'SubscriberIdentity = 310150000000001', out)


if __name__ == '__main__':
    # avoid writing to stderr
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
