"""Microphone mute via the Windows Core Audio API (pycaw)."""
from __future__ import annotations

from visualcommand.actions.base import register_action


def _mic_volume():
    import comtypes
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    comtypes.CoInitialize()  # safe to call repeatedly on the worker thread
    device = AudioUtilities.GetMicrophone()
    if device is None:
        raise RuntimeError("No microphone found")
    iface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return iface.QueryInterface(IAudioEndpointVolume)


@register_action("mute_mic", "Mute / unmute microphone",
                 "Toggles mute on the default recording device.", "Audio", order=20)
def mute_mic(ctx, params):
    vol = _mic_volume()
    muted = not bool(vol.GetMute())
    vol.SetMute(muted, None)
    return "Microphone muted" if muted else "Microphone on"
