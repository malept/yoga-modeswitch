#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Mark Lee
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

from collections import namedtuple
from functools import partial
from gi.repository import AppIndicator3 as AppIndicator, GLib, Gtk
from itertools import chain
import socket
import subprocess
import sys
from threading import Thread

Indicator = AppIndicator.Indicator
Category = AppIndicator.IndicatorCategory
Status = AppIndicator.IndicatorStatus

PRGNAME = 'yoga-modeswitch'
PRGTITLE = 'Yoga Mode Switcher'

TOUCHPAD = 'SynPS/2 Synaptics TouchPad'
TOUCHSCREEN = 'ELAN Touchscreen'
TRACKPOINT = 'TPPS/2 IBM TrackPoint'

TS_MATRIX = {
    'normal': [[1, 0, 0],
               [0, 1, 0],
               [0, 0, 1]],
    'right': [[0, 1, 0],
              [-1, 0, 1],
              [0, 0, 1]],
    'left': [[0, -1, 1],
             [1, 0, 0],
             [0, 0, 1]],
    'inverted': [[-1, 0, 1],
                 [0, -1, 1],
                 [0, 0, 1]],
}

acpi_event = namedtuple('ACPIEvent', ['module', 'source', 'code', 'state'])


def run(*args):
    return subprocess.call(list(args))

xinput = partial(run, 'xinput')
xinput_disable = partial(run, 'xinput', 'disable')
xrandr = partial(run, 'xrandr')


class ModeIndicator(object):

    def __init__(self):
        self.indicator = Indicator.new(PRGNAME, 'computer-symbolic',
                                       Category.HARDWARE)
        self.indicator.set_title(PRGTITLE)
        self.indicator.set_status(Status.ACTIVE)
        self.socket_thread = Thread(name='acpid', target=self.acpi_tablet_mode)
        self.socket_thread.start()

    def add_radio_item(self, group, label, toggle_callback, **kwargs):
        item = Gtk.RadioMenuItem.new_with_label(group, label)
        for k, v in kwargs.items():
            setattr(item, k, v)
        item.connect('toggled', toggle_callback)
        group.append(item)
        self.menu.append(item)
        return item

    def add_separator_item(self, label):
        self.menu.append(Gtk.SeparatorMenuItem(label))

    def build_menu(self):

        self.menu = Gtk.Menu()

        group = []
        self.add_separator_item('Type')
        add_item = partial(self.add_radio_item,
                           toggle_callback=self.on_type_toggled)
        add_item(group, 'Laptop Mode', mode_type='laptop')
        add_item(group, 'Tablet Mode', mode_type='tablet')

        self.orientation_group = []
        self.add_separator_item('Tablet Orientation')
        add_item = partial(self.add_radio_item,
                           toggle_callback=self.on_orientation_toggled)
        add_item(self.orientation_group, 'Windows Button on Bottom',
                 orientation='normal')
        add_item(self.orientation_group, 'Windows Button to the Right',
                 orientation='right')
        add_item(self.orientation_group, 'Windows Button on Top',
                 orientation='inverted')
        add_item(self.orientation_group, 'Windows Button to the Left',
                 orientation='left')

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def switch_mode(self, tablet):
        if tablet:  # disable touchpad and trackpoint
            xinput('disable', TOUCHPAD)
            xinput('disable', TRACKPOINT)
            self.indicator.set_icon('computer-apple-ipad-symbolic')
        else:
            xinput('enable', TOUCHPAD)
            xinput('enable', TRACKPOINT)
            self.indicator.set_icon('computer-symbolic')

    def on_type_toggled(self, item):
        if item.get_active():
            self.switch_mode(item.mode_type == 'tablet')

    def switch_orientation(self, orientation):
        xrandr('--orientation', orientation)
        xinput('set-prop', TOUCHSCREEN, 'Coordinate Transformation Matrix',
               *[str(c) for c in chain(*TS_MATRIX[orientation])])

    def on_orientation_toggled(self, item):
        if item.get_active():
            self.switch_orientation(item.orientation)

    def acpi_tablet_mode(self):
        sock = socket.socket(socket.AF_UNIX)
        try:
            sock.connect('/var/run/acpid.socket')
        except socket.error, msg:
            # TODO error dialog?
            print('ERROR connecting to acpid: {0}'.format(msg),
                  file=sys.stderr)
            raise
        else:
            msg = sock.recv(200)
            while msg:
                event = acpi_event(*msg.strip().split(' '))
                if event.module == 'video/tabletmode' and \
                   event.source == 'TBLT':
                    self.switch_mode(event.state == '00000001')
                msg = sock.recv(200)


def main(argv):
    Gtk.init()
    GLib.set_prgname(PRGNAME)
    GLib.set_application_name(PRGTITLE)
    indicator = ModeIndicator()
    indicator.build_menu()

    Gtk.main()
    return 0;

if __name__ == '__main__':
    sys.exit(main(sys.argv))
