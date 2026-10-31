"""Choosing a microphone and speaker other than the system defaults, for use without the robot."""

from __future__ import annotations

import itertools
import json
import logging
import os
import re
import subprocess
import sys
from typing import Any, Callable

from .desktop import children

logger = logging.getLogger(__name__)

INPUT_SETTING = "AUDIO_INPUT_DEVICE"
OUTPUT_SETTING = "AUDIO_OUTPUT_DEVICE"
_SETTING_FOR = {"Source": INPUT_SETTING, "Sink": OUTPUT_SETTING}

_PKEY_DEVICE_DESCRIPTION = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
_PKEY_INTERFACE_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
_DEVICE_STATE_ACTIVE = 1


def _windows_endpoints(kind: str) -> list[str]:
    """Connected "Capture" or "Render" endpoints, read from the registry."""
    import winreg

    names = set()
    base = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\{kind}"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as root:
        for i in itertools.count():
            try:
                guid = winreg.EnumKey(root, i)
            except OSError:
                break
            try:
                with winreg.OpenKey(root, guid) as device:
                    if winreg.QueryValueEx(device, "DeviceState")[0] != _DEVICE_STATE_ACTIVE:
                        continue
                    with winreg.OpenKey(device, "Properties") as props:
                        description = winreg.QueryValueEx(props, _PKEY_DEVICE_DESCRIPTION)[0]
                        interface = winreg.QueryValueEx(props, _PKEY_INTERFACE_NAME)[0]
            except OSError:
                continue
            names.add(f"{description} ({interface})")
    return sorted(names)


def _gst_devices(device_class: str) -> list[Any]:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst

    Gst.init(None)
    monitor = Gst.DeviceMonitor()
    monitor.add_filter(device_class, None)
    monitor.start()
    try:
        return list(monitor.get_devices())
    finally:
        monitor.stop()


def _records_the_speakers(device: Any) -> bool:
    props = device.get_properties()
    if props is None:
        return False
    loopback = props.has_field("wasapi2.device.loopback") and str(props.get_value("wasapi2.device.loopback")).lower() == "true"
    monitor = props.has_field("device.class") and props.get_value("device.class") == "monitor"
    return loopback or monitor


def _names(devices: list[Any]) -> list[str]:
    return sorted({d.get_display_name() for d in devices if d.get_display_name()})


def list_devices() -> dict[str, list[str]]:
    if sys.platform == "win32":
        return {"inputs": _windows_endpoints("Capture"), "outputs": _windows_endpoints("Render")}
    return {
        "inputs": _names([d for d in _gst_devices("Audio/Source") if not _records_the_speakers(d)]),
        "outputs": _names(_gst_devices("Audio/Sink")),
    }


def list_devices_safely(timeout: float = 20.0) -> dict[str, list[str]]:
    """``list_devices`` from inside the running app, in a fresh process outside Windows."""
    if sys.platform == "win32":
        return list_devices()
    result = subprocess.run(
        children.command(children.DEVICES_MODULE), capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, creationflags=children.NO_WINDOW,
    )
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if result.returncode != 0 or not lines:
        raise RuntimeError((result.stderr or "listing devices failed").strip().splitlines()[-1])
    return json.loads(lines[-1])


def _without_instance_number(name: str) -> str:
    return " ".join(re.sub(r"\(\d+- ", "(", name).lower().split())


def _matching(devices: list[Any], name: str) -> Any | None:
    """The device called ``name``, or one with the same description on another interface."""
    wanted = _without_instance_number(name)
    for device in devices:
        if _without_instance_number(device.display_name) == wanted:
            return device
    description = wanted.split(" (")[0]
    return next((d for d in devices if _without_instance_number(d.display_name).split(" (")[0] == description), None)


def chosen(setting: str) -> str:
    return (os.getenv(setting) or "").strip()


def _wrap_lookup(original: Callable[[str], str | None]) -> Callable[[str], str | None]:
    def get_audio_device(device_type: str = "Source") -> str | None:
        name = chosen(_SETTING_FOR.get(device_type, ""))
        if name:
            from reachy_mini.media.device_detection import find_audio_device, gst_monitor_devices

            device = _matching(gst_monitor_devices(f"Audio/{device_type}"), name)
            device_id = device and find_audio_device([device], device_type, target_name=device.display_name)
            if device_id:
                logger.info("Using the chosen %s: %s", "microphone" if device_type == "Source" else "speaker", name)
                return device_id
            logger.warning("The chosen %s %r isn't connected; using the default", device_type.lower(), name)
        return original(device_type)

    return get_audio_device


def use_chosen_audio(*modules: Any) -> None:
    """Route the SDK's audio device lookup in these modules through the user's choice."""
    for module in modules:
        module.get_audio_device = _wrap_lookup(module.get_audio_device)


def _source_element(gst: Any, device_id: str) -> Any:
    if sys.platform == "win32":
        source = gst.ElementFactory.make("wasapi2src")
        source.set_property("device", device_id)
    elif sys.platform == "darwin":
        source = gst.ElementFactory.make("osxaudiosrc")
        source.set_property("unique-id", device_id)
    else:
        source = gst.ElementFactory.make("pulsesrc")
        source.set_property("device", device_id)
    return source


class _ChosenSourceGst:
    """Stands in for Gst while the SDK builds its mic chain: the default source becomes the chosen mic."""

    def __init__(self, gst: Any, device_id: str) -> None:
        self._gst = gst
        self._device_id = device_id
        self.ElementFactory = self

    def make(self, factory: str, name: str | None = None) -> Any:
        if factory == "autoaudiosrc":
            return _source_element(self._gst, self._device_id)
        return self._gst.ElementFactory.make(factory, name)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._gst, attr)


def cancel_echo_on_chosen_mic(module: Any) -> None:
    """Keep the SDK's echo cancellation, which it only pairs with the default mic, on a chosen mic."""
    cls = module.GStreamerAudio
    original = cls._init_pipeline_record

    def init_pipeline_record(self: Any, pipeline: Any) -> None:
        name = chosen(INPUT_SETTING)
        device_id = module.get_audio_device("Source") if name else None
        if not device_id or "reachy" in name.lower() or module.has_reachymini_asoundrc():
            original(self, pipeline)
            return
        lookup, gst = module.get_audio_device, module.Gst
        module.get_audio_device = lambda device_type="Source": None if device_type == "Source" else lookup(device_type)
        module.Gst = _ChosenSourceGst(gst, device_id)
        try:
            original(self, pipeline)
        finally:
            module.get_audio_device, module.Gst = lookup, gst

    cls._init_pipeline_record = init_pipeline_record


if __name__ == "__main__":
    print(json.dumps(list_devices()), flush=True)
