'''evolution-data-server mock template
'''

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3 of the License, or (at your option) any
# later version.  See http://www.gnu.org/copyleft/lgpl.html for the full text
# of the license.

__author__ = 'Jonas Ådahl'
__copyright__ = '(c) Red Hat'


BUS_NAME = 'org.gnome.evolution.dataserver.Sources5'
MAIN_OBJ = '/org/gnome/evolution/dataserver/SourceManager'
MAIN_IFACE = 'org.gnome.evolution.dataserver.SourceManager'
SYSTEM_BUS = False
IS_OBJECT_MANAGER = True


def load(_mock, _parameters):
    pass
