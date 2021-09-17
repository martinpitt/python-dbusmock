'''systemd mock template
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Jonas Ådahl'
__copyright__ = '(c) 2021 Red Hat'

from gi.repository import GLib
import dbus

from dbusmock import MOCK_IFACE, mockobject

BUS_PREFIX = 'org.freedesktop.systemd1'
PATH_PREFIX = '/org/freedesktop/systemd1'


BUS_NAME = BUS_PREFIX
MAIN_OBJ = PATH_PREFIX
MAIN_IFACE = BUS_PREFIX + '.Manager'
UNIT_IFACE = BUS_PREFIX + '.Unit'
SYSTEM_BUS = True


def load(mock, _parameters):
    mock.next_job_id = 1
    mock.units = {}

    mock.AddProperties(MAIN_IFACE, {'Version': 'v246'})


def escape_unit_name(name):
    for s in ['.', '-']:
        name = name.replace(s, '_')
    return name


def emit_job_new_remove(mock, job_id, job_path, name):
    mock.EmitSignal(MAIN_IFACE, 'JobNew', 'uos', [job_id, job_path, name])
    mock.EmitSignal(MAIN_IFACE, 'JobRemoved', 'uoss',
                    [job_id, job_path, name, 'done'])


@dbus.service.method(MAIN_IFACE, in_signature='ss', out_signature='o')
def StartUnit(self, name, _mode):
    job_id = self.next_job_id
    self.next_job_id += 1

    job_path = f'{PATH_PREFIX}/Job/{job_id}'
    GLib.idle_add(lambda: emit_job_new_remove(self, job_id, job_path, name))

    unit_path = self.units[str(name)]
    unit = mockobject.objects[unit_path]
    unit.UpdateProperties(UNIT_IFACE, {'ActiveState': 'active'})

    return job_path


@dbus.service.method(MAIN_IFACE, in_signature='ssa(sv)a(sa(sv))', out_signature='o')
def StartTransientUnit(self, name, _mode, _properties, _aux):
    job_id = self.next_job_id
    self.next_job_id += 1

    job_path = f'{PATH_PREFIX}/Job/{job_id}'
    GLib.idle_add(lambda: emit_job_new_remove(self, job_id, job_path, name))

    return job_path


@dbus.service.method(MAIN_IFACE, in_signature='ss', out_signature='o')
def StopUnit(self, name, _mode):
    job_id = self.next_job_id
    self.next_job_id += 1

    job_path = f'{PATH_PREFIX}/Job/{job_id}'
    GLib.idle_add(lambda: emit_job_new_remove(self, job_id, job_path, name))

    unit_path = self.units[str(name)]
    unit = mockobject.objects[unit_path]
    unit.UpdateProperties(UNIT_IFACE, {'ActiveState': 'inactive'})
    return job_path


@dbus.service.method(MAIN_IFACE, in_signature='s', out_signature='o')
def GetUnit(self, name):
    unit_path = self.units[str(name)]
    return unit_path


@dbus.service.method(MOCK_IFACE, in_signature='s')
def AddMockUnit(self, name):
    unit_path = f'{PATH_PREFIX}/unit/{escape_unit_name(name)}'
    self.units[str(name)] = unit_path
    self.AddObject(unit_path,
                   UNIT_IFACE,
                   {
                       'Id': name,
                       'Names': [name],
                       'LoadState': 'loaded',
                       'ActiveState': 'inactive',
                   },
                   [])
