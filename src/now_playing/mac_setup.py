"""Compatibility import for older Mac setup scripts."""

from .devices import select_microphone


def microphone_settings(devices, default_input, requested=None):
    return select_microphone(devices, default_input, requested, platform="darwin")
