# -*- coding: utf-8; -*-

# Copyright (C) 2015 - 2024 Lionel Ott
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


import collections
from collections.abc import Callable
import functools
import heapq
import inspect
import logging
import time
import threading
import uuid

from PySide6 import QtCore

import gremlin.common
import gremlin.keyboard
import gremlin.types
from dill import UUID_Invalid

from gremlin import common, error, event_handler, joystick_handling, \
    mode_manager
from gremlin.input_cache import Joystick, Keyboard


class CallbackRegistry:

    """Registry of all callbacks known to the system."""

    def __init__(self):
        """Creates a new callback registry instance."""
        self._registry = {}
        self._current_id = 0

    def add(self, callback, event, mode):
        """Adds a new callback to the registry.

        :param callback function to add as a callback
        :param event the event on which to trigger the callback
        :param mode the mode in which to trigger the callback
        """
        self._current_id += 1
        function_name = "{}_{:d}".format(callback.__name__, self._current_id)

        if event.device_guid not in self._registry:
            self._registry[event.device_guid] = {}
        if mode not in self._registry[event.device_guid]:
            self._registry[event.device_guid][mode] = {}

        if event not in self._registry[event.device_guid][mode]:
            self._registry[event.device_guid][mode][event] = {}
        self._registry[event.device_guid][mode][event][function_name] = callback

    @property
    def registry(self):
        """Returns the registry dictionary.

        :return registry dictionary
        """
        return self._registry

    def clear(self):
        """Clears the registry entries."""
        self._registry = {}


class PeriodicRegistry:

    """Registry for periodically executed functions."""

    def __init__(self):
        """Creates a new instance."""
        self._registry = {}
        self._running = False
        self._thread = threading.Thread(target=self._thread_loop)
        self._queue = []
        self._plugins = []

    def start(self):
        """Starts the event loop."""
        # Only proceed if we have functions to call
        if len(self._registry) == 0:
            return

        # Only create a new thread and start it if the thread is not
        # currently running
        self._running = True
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._thread_loop)
            self._thread.start()

    def stop(self):
        """Stops the event loop."""
        self._running = False
        if self._thread.is_alive():
            self._thread.join()

    def add(self, callback, interval):
        """Adds a function to execute periodically.

        :param callback the function to execute
        :param interval the time between executions
        """
        self._registry[callback] = (interval, callback)

    def clear(self):
        """Clears the registry."""
        self._registry = {}

    def _install_plugins(self, callback):
        """Installs the current plugins into the given callback.

        :param callback the callback function to install the plugins
            into
        :return new callback with plugins installed
        """
        signature = inspect.signature(callback).parameters
        partial_fn = functools.partial
        if "self" in signature:
            partial_fn = functools.partialmethod
        for plugin in self._plugins:
            if plugin.keyword in signature:
                callback = plugin.install(callback, partial_fn)
        return callback

    def _thread_loop(self):
        """Main execution loop run in a separate thread."""
        # Setup plugins to use
        self._plugins = [
            JoystickPlugin(),
            VJoyPlugin(),
            KeyboardPlugin()
        ]
        callback_map = {}

        # Populate the queue
        self._queue = []
        for item in self._registry.values():
            plugin_cb = self._install_plugins(item[1])
            callback_map[plugin_cb] = item[0]
            heapq.heappush(
                self._queue,
                (time.time() + callback_map[plugin_cb], plugin_cb)
            )

        # Main thread loop
        while self._running:
            # Process all events that require running
            while self._queue[0][0] < time.time():
                item = heapq.heappop(self._queue)
                item[1]()

                heapq.heappush(
                    self._queue,
                    (time.time() + callback_map[item[1]], item[1])
                )

            # Sleep until either the next function needs to be run or
            # our timeout expires
            time.sleep(min(self._queue[0][0] - time.time(), 1.0))


# Global registry of all registered callbacks
callback_registry = CallbackRegistry()

# Global registry of all periodic callbacks
periodic_registry = PeriodicRegistry()


# def register_callback(callback, device, input_type, input_id):
#     """Adds a callback to the registry.
#
#     This function adds the provided callback to the global callback_registry
#     for the specified event and mode combination.
#
#     Parameters
#     ==========
#     callback : callable
#         The callable object to execute when the event with the specified
#         conditions occurs
#     device : JoystickDecorator
#         Joystick decorator specifying the device and mode in which to execute
#         the callback
#     input_type : gremlin.types.InputType
#         Type of input on which to execute the callback
#     input_id : int
#         Index of the input on which to execute the callback
#     """
#     event = event_handler.Event(
#         event_type=input_type,
#         device_guid=device.device_guid,
#         identifier=input_id
#     )
#     callback_registry.add(callback, event, device.mode, False)


class VJoyPlugin:

    """Plugin providing automatic access to the VJoyProxy object.

    For a function to use this plugin it requires one of its parameters
    to be named "vjoy".
    """

    vjoy = joystick_handling.VJoyProxy()

    def __init__(self):
        self.keyword = "vjoy"

    def install(self, callback, partial_fn):
        """Decorates the given callback function to provide access to
        the VJoyProxy object.

        Only if the signature contains the plugin's keyword is the
        decorator applied.

        :param callback the callback to decorate
        :param partial_fn function to create the partial function / method
        :return callback with the plugin parameter bound
        """
        return partial_fn(callback, vjoy=VJoyPlugin.vjoy)


class JoystickPlugin:

    """Plugin providing automatic access to the Joystick object.

    For a function to use this plugin it requires one of its parameters
    to be named "joy".
    """

    joystick = Joystick()

    def __init__(self):
        self.keyword = "joy"

    def install(self, callback, partial_fn):
        """Decorates the given callback function to provide access
        to the Joystick object.

        Only if the signature contains the plugin's keyword is the
        decorator applied.

        :param callback the callback to decorate
        :param partial_fn function to create the partial function / method
        :return callback with the plugin parameter bound
        """
        return partial_fn(callback, joy=JoystickPlugin.joystick)


class KeyboardPlugin:

    """Plugin providing automatic access to the Keyboard object.

    For a function to use this plugin it requires one of its parameters
    to be named "keyboard".
    """

    keyboard = Keyboard()

    def __init__(self):
        self.keyword = "keyboard"

    def install(self, callback, partial_fn):
        """Decorates the given callback function to provide access to
        the Keyboard object.

        :param callback the callback to decorate
        :param partial_fn function to create the partial function / method
        :return callback with the plugin parameter bound
        """
        return partial_fn(callback, keyboard=KeyboardPlugin.keyboard)


class JoystickDecorator:

    """Creates customized decorators for physical joystick devices."""

    def __init__(self, name: str, device_guid: str, mode: str):
        """Creates a new instance with customized decorators.

        :param name the name of the device
        :param device_guid the device id in the system
        :param mode the mode in which the decorated functions
            should be active
        """
        self.name = name
        self.mode = mode
        # Convert string based GUID to the actual GUID object
        try:
            self.device_guid = uuid.UUID(device_guid)
        except error.ProfileError:
            logging.getLogger("system").error(
                f"Invalid guid value '{device_guid}' received."
            )
            self.device_guid = UUID_Invalid

        self.axis = functools.partial(
            _axis, device_guid=self.device_guid, mode=mode
        )
        self.button = functools.partial(
            _button, device_guid=self.device_guid, mode=mode
        )
        self.hat = functools.partial(
            _hat, device_guid=self.device_guid, mode=mode
        )


ButtonReleaseEntry = collections.namedtuple(
    "Entry", ["callback", "event", "mode"]
)


@common.SingletonDecorator
class ButtonReleaseActions(QtCore.QObject):

    """Ensures a desired action is run when a button is released."""

    def __init__(self):
        """Initializes the instance."""
        QtCore.QObject.__init__(self)

        self._registry = {}
        el = event_handler.EventListener()
        el.joystick_event.connect(self._input_event_cb)
        el.keyboard_event.connect(self._input_event_cb)
        el.virtual_event.connect(self._input_event_cb)
        mm = mode_manager.ModeManager()
        self._current_mode = mm.current.name
        mm.mode_changed.connect(self._mode_changed_cb)

    def register_callback(
        self,
        callback: Callable[[], None],
        physical_event: event_handler.Event
    ) -> None:
        """Registers a callback with the system.

        Args:
            callback: the function to run when the corresponding button is
                released
            physical_event: the physical event of the button being pressed
        """
        release_evt = physical_event.clone()
        release_evt.is_pressed = False

        if release_evt not in self._registry:
            self._registry[release_evt] = []
        # Do not record the mode since we may want to run the release action
        # independent of a mode
        self._registry[release_evt].append(
            ButtonReleaseEntry(callback, release_evt, None)
        )

    def register_button_release(
        self,
        vjoy_input: int,
        physical_event: event_handler.Event,
        activate_on: bool
    ):
        """Registers a physical and vjoy button pair for tracking.

        This method ensures that a vjoy button is pressed/released when the
        specified physical event occurs next. This is useful for cases where
        an action was triggered in a different mode or using a different
        condition.

        Args:
            vjoy_input: the vjoy button to release, represented as
                (vjoy_device_id, vjoy_button_id)
            physical_event: the button event when release should
                trigger the release of the vjoy button
        """
        release_evt = physical_event.clone()
        release_evt.is_pressed = activate_on

        if release_evt not in self._registry:
            self._registry[release_evt] = []
        # Record current mode so we only release if we've changed mode
        self._registry[release_evt].append(ButtonReleaseEntry(
            lambda: self._release_callback_prototype(vjoy_input),
            release_evt,
            self._current_mode
        ))

    def _release_callback_prototype(self, vjoy_input: int) -> None:
        """Prototype of a button release callback, used with lambdas.

        Args:
            vjoy_input: the vjoy input data to use in the release
        """
        vjoy = joystick_handling.VJoyProxy()
        # Check if the button is valid otherwise we cause Gremlin to crash
        if vjoy[vjoy_input[0]].is_button_valid(vjoy_input[1]):
            vjoy[vjoy_input[0]].button(vjoy_input[1]).is_pressed = False
        else:
            logging.getLogger("system").warning(
                f"Attempted to use non existent button: " +
                f"vJoy {vjoy_input[0]:d} button {vjoy_input[1]:d}"
            )

    def _input_event_cb(self, event: event_handler.Event):
        """Runs callbacks associated with the given event.

        Args:
            event: the event to process
        """
        #if evt in [e for e in self._registry if e.is_pressed != evt.is_pressed]:
        if event in self._registry:
            new_list = []
            for entry in self._registry[event]:
                if entry.event.is_pressed == event.is_pressed:
                    entry.callback()
                else:
                    new_list.append(entry)
            self._registry[event] = new_list

    def _mode_changed_cb(self, mode: str) -> None:
        """Updates the current mode variable.

        Args:
            mode: name of the now active mode
        """
        self._current_mode = mode


@common.SingletonDecorator
class JoystickInputSignificant:

    """Checks whether or not joystick inputs are significant."""

    def __init__(self):
        """Initializes the instance."""
        self._event_registry = {}
        self._mre_registry = {}
        self._time_registry = {}

    def should_process(self, event: event_handler.Event) -> bool:
        """Returns whether or not a particular event is significant enough to
        process.

        Args:
            event: the event to check for significance

        Returns:
            True if the event should be processed, False otherwise
        """
        self._mre_registry[event] = event

        if event.event_type == gremlin.types.InputType.JoystickAxis:
            return self._process_axis(event)
        elif event.event_type == gremlin.types.InputType.JoystickButton:
            return self._process_button(event)
        elif event.event_type == gremlin.types.InputType.JoystickHat:
            return self._process_hat(event)
        else:
            logging.getLogger("system").warning(
                "Event with unknown type received"
            )
            return False

    def last_event(self, event: event_handler.Event) -> event_handler.Event:
        """Returns the most recent event of this type.

        Args:
            event: the type of event for which to return the most recent one

        Returns:
            Latest event instance corresponding to the specified event
        """
        return self._mre_registry[event]

    def reset(self) -> None:
        """Resets the detector to a clean state for subsequent uses."""
        self._event_registry = {}
        self._mre_registry = {}
        self._time_registry = {}

    def _process_axis(self, event: event_handler.Event) -> bool:
        """Process an axis event.

        Args:
            event: the axis event to process

        Returns:
            True if it should be processed, False otherwise
        """
        if event in self._event_registry:
            # Reset everything if we have no recent data
            if self._time_registry[event] + 5.0 < time.time():
                self._event_registry[event] = event
                self._time_registry[event] = time.time()
                return False
            # Update state
            else:
                self._time_registry[event] = time.time()
                if abs(self._event_registry[event].value - event.value) > 0.25:
                    self._event_registry[event] = event
                    self._time_registry[event] = time.time()
                    return True
                else:
                    return False
        else:
            self._event_registry[event] = event
            self._time_registry[event] = time.time()
            return False

    def _process_button(self, event: event_handler.Event) -> bool:
        """Process a button event.

        Args:
            event: the button event to process

        Returns:
            True if it should be processed, False otherwise
        """
        return True

    def _process_hat(self, event: event_handler.Event) -> bool:
        """Process a hat event.

        Args:
            event: the hat event to process

        Returns:
            True if it should be processed, False otherwise
        """
        return event.value != (0, 0)


def _button(button_id, device_guid, mode):
    """Decorator for button callbacks.

    :param button_id the id of the button on the physical joystick
    :param device_guid the GUID of input device
    :param mode the mode in which this callback is active
    """

    def wrap(callback):

        @functools.wraps(callback)
        def wrapper_fn(*args, **kwargs):
            callback(*args, **kwargs)

        event = event_handler.Event(
            event_type=gremlin.types.InputType.JoystickButton,
            device_guid=device_guid,
            identifier=button_id
        )
        callback_registry.add(wrapper_fn, event, mode)

        return wrapper_fn

    return wrap


def _hat(hat_id, device_guid, mode):
    """Decorator for hat callbacks.

    :param hat_id the id of the button on the physical joystick
    :param device_guid the GUID of input device
    :param mode the mode in which this callback is active
    """

    def wrap(callback):

        @functools.wraps(callback)
        def wrapper_fn(*args, **kwargs):
            callback(*args, **kwargs)

        event = event_handler.Event(
            event_type=gremlin.types.InputType.JoystickHat,
            device_guid=device_guid,
            identifier=hat_id
        )
        callback_registry.add(wrapper_fn, event, mode)

        return wrapper_fn

    return wrap


def _axis(axis_id, device_guid, mode):
    """Decorator for axis callbacks.

    :param axis_id the id of the axis on the physical joystick
    :param device_guid the GUID of input device
    :param mode the mode in which this callback is active
    """

    def wrap(callback):

        @functools.wraps(callback)
        def wrapper_fn(*args, **kwargs):
            callback(*args, **kwargs)

        event = event_handler.Event(
            event_type=gremlin.types.InputType.JoystickAxis,
            device_guid=device_guid,
            identifier=axis_id
        )
        callback_registry.add(wrapper_fn, event, mode)

        return wrapper_fn

    return wrap


def keyboard(key_name, mode):
    """Decorator for keyboard key callbacks.

    :param key_name name of the key of this callback
    :param mode the mode in which this callback is active
    """

    def wrap(callback):

        @functools.wraps(callback)
        def wrapper_fn(*args, **kwargs):
            callback(*args, **kwargs)

        key = gremlin.keyboard.key_from_name(key_name)
        event = event_handler.Event.from_key(key)
        callback_registry.add(wrapper_fn, event, mode)

        return wrapper_fn

    return wrap


def periodic(interval: float):
    """Decorator for periodic function callbacks.

    Args:
        interval: the duration between executions of the function
    """

    def wrap(callback):

        @functools.wraps(callback)
        def wrapper_fn(*args, **kwargs):
            callback(*args, **kwargs)

        periodic_registry.add(wrapper_fn, interval)

        return wrapper_fn

    return wrap


def squash(value: float, func: Callable[[float], float]) -> float:
    """Returns the appropriate function value when the function is
    squashed to [-1, 1].

    Args:
        value: the function value to compute
        func: the function whose output is to be squashed

    Returns:
        Function value at value after squashing to [-1, 1]
    """
    return (2 * func(value)) / abs(func(-1) - func(1))


def deadzone(
        value: float,
        low: float,
        low_center: float,
        high_center: float,
        high: float
) -> float:
    """Returns the mapped value taking the provided deadzone into
    account.

    The following relationship between the limits has to hold.
    -1 <= low < low_center <= 0 <= high_center < high <= 1

    Args:
        value: the raw input value
        low: low deadzone limit
        low_center: lower center deadzone limit
        high_center: upper center deadzone limit
        high: high deadzone limit

    Returns:
        Corrected value
    """
    if value >= 0:
        return min(1.0, max(0.0, (value - high_center) / abs(high - high_center)))
    else:
        return max(-1.0, min(0.0, (value - low_center) / abs(low - low_center)))


def format_input(event: event_handler.Event) -> str:
    """Formats the input specified the device and event into a string.

    Args:
        event: event to format

    Returns:
        Textual representation of the event
    """
    # Retrieve device instance belonging to this event
    device = None
    for dev in joystick_handling.joystick_devices():
        if dev.device_guid == event.device_guid:
            device = dev
            break

    # Retrieve device name
    label = ""
    if device is None:
        logging.warning(
            f"Unable to find a device with GUID {str(event.device_guid)}"
        )
        label = "Unknown"
    else:
        label = device.name

    # Retrive input name
    label += " - "
    label += gremlin.common.input_to_ui_string(
        event.event_type,
        event.identifier
    )

    return label
