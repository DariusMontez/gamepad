# -*- coding: utf-8 -*-

"""Main module."""

from __future__ import print_function

import os
import struct
import array
import threading
from fcntl import ioctl


axis_names = {
    0x00: 'x',
    0x01: 'y',
    0x02: 'z',
    0x03: 'rx',
    0x04: 'ry',
    0x05: 'rz',
    0x06: 'throttle',
    0x07: 'rudder',
    0x08: 'wheel',
    0x09: 'gas',
    0x0a: 'brake',
    0x10: 'hat0x',
    0x11: 'hat0y',
    0x12: 'hat1x',
    0x13: 'hat1y',
    0x14: 'hat2x',
    0x15: 'hat2y',
    0x16: 'hat3x',
    0x17: 'hat3y',
    0x18: 'pressure',
    0x19: 'distance',
    0x1a: 'tilt_x',
    0x1b: 'tilt_y',
    0x1c: 'tool_width',
    0x20: 'volume',
    0x28: 'misc',
}

button_names = {
    0x120: 'trigger',
    0x121: 'thumb',
    0x122: 'thumb2',
    0x123: 'top',
    0x124: 'top2',
    0x125: 'pinkie',
    0x126: 'base',
    0x127: 'base2',
    0x128: 'base3',
    0x129: 'base4',
    0x12a: 'base5',
    0x12b: 'base6',
    0x12f: 'dead',
    0x130: 'a',
    0x131: 'b',
    0x132: 'c',
    0x133: 'x',
    0x134: 'y',
    0x135: 'z',
    0x136: 'tl',
    0x137: 'tr',
    0x138: 'tl2',
    0x139: 'tr2',
    0x13a: 'select',
    0x13b: 'start',
    0x13c: 'mode',
    0x13d: 'thumbl',
    0x13e: 'thumbr',

    0x220: 'dpad_up',
    0x221: 'dpad_down',
    0x222: 'dpad_left',
    0x223: 'dpad_right',

    # XBox 360 controller uses these codes.
    0x2c0: 'dpad_left',
    0x2c1: 'dpad_right',
    0x2c2: 'dpad_up',
    0x2c3: 'dpad_down',
}

common_names = {
  "trigger":    "btn1",
  "thumb":      "btn2",
  "thumb2":     "btn3",
  "top":        "btn4",
  # "top2":       "btn5",
  # "pinkie":     "btn6",
  # "base":       "btn7",
  # "base2":      "btn8",
  # "base3":      "btn9",
  # "base4":      "btn10",
  "base5":      "btn11",
  "base6":      "btn12",

  "base":       "l1",
  "top2":       "l2",
  "base2":      "r1",
  "pinkie":     "r2",
  "base3":      "select",
  "base4":      "start",
  "dpad_left":  "dpad_left",
  "dpad_up": "dpad_up",
  "dpad_right": "dpad_right",
  "dpad_down": "dpad_down",
  "hat0x": "dpadx",
  "hat0y": "dpady",
  "x": "lx",
  "y": "ly",
  "rz": "rx",
  "z": "ry",
}

device_name_keywords = (
  "game",
  "gaming",
  "gamepad",
  "controller",
  "joystick",
)


class Handler:
    def __init__(self, event, fn, *args, **kwargs):
        self.event = event
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *a, **kw):
        return self.fn(*(self.args + a), **dict(self.kwargs, **kw))


class Gamepad:

    def __init__(self, device=None):

        self._device = device
        self._file = None
        self._name = ""
        self._handlers = []
        self._connected = False

        self._num_axes = 0
        self._axis_map = []
        self._axis_states = {}

        self._num_buttons = 0
        self._button_map = []
        self._button_states = {}

        self._thread = threading.Thread(target=self._thread_worker)
        self._thread.setDaemon(True)
        self._thread.start()

    # private methods

    def _get_device_list(self):
        for filename in os.listdir("/dev/input"):
            if filename.startswith("js"):
                yield os.path.join("/dev/input", filename)

    def _open_device(self, device):
        return open(device, "rb")

    def _get_name(self, _file):
        buf = array.array('B', [0] * 64)
        ioctl(_file, 0x80006a13 + (0x10000 * len(buf)), buf)
        return buf.tobytes().decode("utf-8")

    def _get_num_axes(self, _file):
        buf = array.array('B', [0])
        ioctl(_file, 0x80016a11, buf)  # JSIOCGAXES
        return buf[0]

    def _get_num_buttons(self, _file):
        buf = array.array('B', [0])
        ioctl(_file, 0x80016a12, buf)  # JSIOCGBUTTONS
        return buf[0]

    def _init_axis_map(self, _file):
        buf = array.array('B', [0] * 0x40)
        ioctl(_file, 0x80406a32, buf)  # JSIOCGAXMAP

        for axis in buf[:self._get_num_axes(_file)]:
            axis_name = axis_names.get(axis, 'unknown(0x%02x)' % axis)
            self._axis_map.append(axis_name)
            self._axis_states[axis_name] = 0.0

    def _init_button_map(self, _file):
        buf = array.array('H', [0] * 200)
        ioctl(_file, 0x80406a34, buf)  # JSIOCGBTNMAP

        for button in buf[:self._get_num_buttons(_file)]:
            button_name = button_names.get(button, 'unknown(0x%03x)' % button)
            self._button_map.append(button_name)
            self._button_states[button_name] = False

    # event handlers
    def _handle_button_event(self, button, value):
        for h in self._handlers:
            if (
              h.event == common_names[button] or
              h.event == common_names[button] + ":pressed"):

                h(value, h.event)

    def _handle_button_released_event(self, button, value):
        for h in self._handlers:
            if h.event == common_names[button] + ":released":
                h(value, h.event)

    def _handle_button_changed_event(self, button, value):
        for h in self._handlers:
            if h.event == common_names[button] + ":changed":
                h(value, h.event)

    def _handle_axis_event(self, axis, value):
        for h in self._handlers:
            if h.event == common_names[axis]:
                h(value, h.event)

    def _read_device(self):
        event_buf = self._file.read(8)
        if (event_buf):
            ts, value, event_type, number = struct.unpack("IhBB", event_buf)

            if event_type & 0x80:  # initial reading
                return

            if event_type & 0x81:  # button
                button = self._button_map[number]
                if button:
                    self._button_states[button] = bool(value)
                    self._handle_button_changed_event(button, value)
                    if value:
                        self._handle_button_event(button, value)
                    else:
                        self._handle_button_released_event(button, value)

            if event_type & 0x02:  # axis
                axis = self._axis_map[number]
                if axis:
                    fvalue = value / 32767.0
                    self._axis_states[axis] = fvalue
                    self._handle_axis_event(axis, fvalue)

    def _connect_to_device(self, device_path):
        _file = self._open_device(device_path)
        name = self._get_name(_file)

        for kw in device_name_keywords:
            if kw in name.lower():
                self._device = device_path
                self._file = _file
                self._connected = True
                self._on_connect()
                return

    def _update_connection(self):
        if not (self._device and
                os.path.exists(self._device) and
                self._connected):

            self._connected = False

            # If the user specifies a device path, use it. Otherwise, make an
            # educated guess

            if self._device:
                self._connect_to_device(self._device)
            else:
                for device_path in self._get_device_list():
                    self._connect_to_device(device_path)

    def _on_connect(self):
        self._init_button_map(self._file)
        self._init_axis_map(self._file)
        self._name = self._get_name(self._file)

        # notify the user that this gamepad is connected

        for handler in self._handlers:
            if handler.event == "connect":
                handler()

    def _on_disconnect(self):
        for handler in self._handlers:
            if handler.event == "disconnect":
                handler()

    def _thread_worker(self, *args):
        while (1):
            try:
                self._update_connection()
                if self._connected:
                    self._read_device()
            except IOError:
                if self.connected:
                    self._on_disconnect()

    # public methods/properties

    @property
    def connected(self):
        return self._connected

    @property
    def device(self):
        return self._device

    @property
    def name(self):
        return self._name

    @property
    def inputs(self):
        return common_names.values()

    def axis(self, axis):
        if self._connected:
            for k, v in self._axis_states.items():
                if common_names[k] == axis:
                    return v
        else:
            return 0.0

    def button(self, button):
        if self._connected:
            for k, v in self._button_states.items():
                if common_names[k] == button:
                    return bool(v)
        else:
            return False

    def on(self, event, handler, *args, **kwargs):
        self._handlers.append(Handler(event, handler, *args, **kwargs))

    def watch_all(self):

        def _on_connect():
            print("Gamepad connected: {}".format(self.name))

        self.on("connect", _on_connect)

        def _on_disconnect():
            print("Gamepad disconnected: {}".format(self.name))

        self.on("disconnect", _on_disconnect)

        def f(value, event):
            print("Gamepad: {} => {}".format(event, value))

        for event in self.inputs:
            self.on(event, f)

            self.on(event+":pressed", f)
            self.on(event+":released", f)
            self.on(event+":changed", f)
