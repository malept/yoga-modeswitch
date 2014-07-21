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

from collections import namedtuple, OrderedDict
from functools import partial
from gi.repository import AppIndicator3 as AppIndicator, GLib, Gtk
from glob import glob
from itertools import chain
import os
import select
import re
import socket
import struct
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

ACCEL_DEVICE = 'accel_3d'
IIO_DIR = '/sys/bus/iio/devices'
BUFFER_LEN = 127

RE_TYPE_DESC = \
    re.compile(r'''
(?P<endian>.)e:
(?P<sign>.)
(?P<bits_used>\d+)/
(?P<padding>\d+)>>
(?P<shift>\d+)
''',
               re.VERBOSE)

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


def find_device_path_by_name(name):
    for ddir in glob(os.path.join(IIO_DIR, 'iio:device*')):
        with open(os.path.join(ddir, 'name')) as f:
            if f.read().strip() == name:
                return ddir
    return None


def run(*args):
    return subprocess.call(list(args))

xinput = partial(run, 'xinput')
xinput_disable = partial(run, 'xinput', 'disable')
xrandr = partial(run, 'xrandr')


class ModeIndicator(object):

    def __init__(self):
        self.tablet_mode = False
        self.orientation = 'normal'
        self.indicator = Indicator.new(PRGNAME, 'computer-symbolic',
                                       Category.HARDWARE)
        self.indicator.set_title(PRGTITLE)
        self.indicator.set_status(Status.ACTIVE)
        self.acpi_thread = Thread(name='acpid', target=self.acpi_tablet_mode)
        self.acpi_thread.start()
        self.sensors_thread = Thread(name='sensors',
                                     target=self.check_orientation_sensors)
        self.sensors_thread.start()

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
            self.switch_orientation('normal')
            self.indicator.set_icon('computer-symbolic')
        self.tablet_mode = tablet

    def on_type_toggled(self, item):
        if item.get_active():
            self.switch_mode(item.mode_type == 'tablet')

    def switch_orientation(self, orientation):
        if orientation == self.orientation:
            return
        xrandr('--orientation', orientation)
        xinput('set-prop', TOUCHSCREEN, 'Coordinate Transformation Matrix',
               *[str(c) for c in chain(*TS_MATRIX[orientation])])
        self.orientation = orientation

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

    @staticmethod
    def _read_sensor_file(base, suffix):
        filename = '{0}_{1}'.format(base, suffix)
        with open(filename, 'rb') as f:
            return f.read()

    @staticmethod
    def _write_to_sensor_file(dirname, basename, value):
        filename = os.path.join(dirname, basename)
        f = os.open(filename, os.O_WRONLY)
        try:
            os.write(f, value)
        finally:
            os.close(f)

    def _get_channel_metadata(self):
        scan_elements_dir = os.path.join(self.device_path, 'scan_elements')
        channel_items = []
        # enable sensors
        for sensor_state_filename in glob(os.path.join(scan_elements_dir,
                                                       '*_en')):
            with open(sensor_state_filename, 'rb') as f:
                sensor_state = int(f.read())
            if not sensor_state:
                with open(sensor_state_filename, 'wb') as f:
                    f.write(b'1')
            base = sensor_state_filename[:-3]
            se_type = self._read_sensor_file(base, 'type')
            match = RE_TYPE_DESC.match(se_type).groupdict()
            bits_used = int(match['bits_used'])
            if bits_used == 64:
                mask = ~0
            else:
                mask = (1 << bits_used) - 1
            channel_items.append({
                'base': base,
                'bigendian': match['endian'] == 'b',
                'bytes': int(match['padding']) / 8,
                'bits_used': bits_used,
                'index': int(self._read_sensor_file(base, 'index')),
                'is_signed': match['sign'] == 's',
                'mask': mask,
                'shift': int(match['shift']),
            })
        return OrderedDict([(d['base'], d)
                            for d in sorted(channel_items,
                                            key=lambda i: i['index'])])

    def _set_trigger_name(self, name):
        trigger_path = os.path.join('trigger', 'current_trigger')
        self._write_to_sensor_file(self.device_path, trigger_path, name)

    def _set_ring_buffer_params(self):
        buffer_len_path = os.path.join('buffer', 'length')
        self._write_to_sensor_file(self.device_path, buffer_len_path,
                                   bytes(BUFFER_LEN + 1))

    @classmethod
    def _enable_buffer(cls, device_path, enabled):
        buffer_enable_path = os.path.join('buffer', 'enable')
        cls._write_to_sensor_file(device_path, buffer_enable_path,
                                  bytes(int(enabled)))

    def _size_from_channels(self, channels):
        size = 0
        for channel in channels.itervalues():
            if size % channel['bytes'] == 0:
                channel['location'] = size
            else:
                channel['location'] = (size - (size % channel['bytes']) +
                                       channel['bytes'])
            size = channel['location'] + channel['bytes']
        return size

    def _process_accel_data(self, channels, data, scan_size):
        # Parse the data into X/Y/Z
        accel_data = {}
        try:
            int_data = struct.unpack('iii', data)
        except struct.error:
            return
        for i, (path, channel) in enumerate(channels.iteritems()):
            value = int_data[i] + channel['location']
            value >>= channel['shift']
            if channel['bits_used'] < 32:
                value &= (1 << channel['bits_used']) - 1
            if channel['is_signed']:
                value = ((value << (32 - channel['bits_used'])) >>
                         (32 - channel['bits_used']))
            accel_data[path[-1]] = value
        if self.tablet_mode:
            if -250 < accel_data['x'] < 250:
                if accel_data['y'] < -750:
                    self.switch_orientation('normal')
                elif accel_data['y'] > 750:
                    self.switch_orientation('inverted')
            elif -250 < accel_data['y'] < 250:  # left or right
                if accel_data['x'] > 750:
                    self.switch_orientation('left')
                elif accel_data['x'] < -750:
                    self.switch_orientation('right')

    def check_orientation_sensors(self):
        self.device_path = find_device_path_by_name(ACCEL_DEVICE)

        channels = self._get_channel_metadata()
        device_num = self.device_path[-1]

        # self._set_trigger_name('{0}-dev{1}'.format(ACCEL_DEVICE, device_num))
        self._set_ring_buffer_params()
        self._enable_buffer(self.device_path, True)
        try:
            scan_size = self._size_from_channels(channels)
            # Read from /dev/iio:device$N
            f = os.open('/dev/iio:device{0}'.format(device_num),
                        os.O_RDONLY | os.O_NONBLOCK)
            try:
                epoll = select.epoll()
                epoll.register(f, select.POLLIN)
                while True:
                    epoll.poll(1, -1)
                    data = os.read(f, scan_size * BUFFER_LEN)
                    if data:
                        self._process_accel_data(channels, data, scan_size)
                    else:
                        print('Nothing available')
            finally:
                os.close(f)
            # Disable the buffer
            self._enable_buffer(self.device_path, False)
        finally:
            # self._set_trigger_name('none')
            self._enable_buffer(self.device_path, False)


def main(argv):
    Gtk.init()
    GLib.set_prgname(PRGNAME)
    GLib.set_application_name(PRGTITLE)
    indicator = ModeIndicator()
    indicator.build_menu()

    Gtk.main()
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
