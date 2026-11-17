# VisualCommand

Hand-gesture shortcuts for Windows, using your webcam. It lives in the system tray (the **^** at the bottom right) and runs an action when you make a gesture: take a screenshot, mute the mic, lock the PC, skip a track, and more.

- **Fully local.** Hand tracking uses Google MediaPipe's on-device model, which ships inside the app. The app makes no network connections.
- **No visual data kept.** Camera frames are analysed in memory and dropped right away. They are never saved, logged or sent anywhere.
- **Camera off means off.** When tracking is off or paused, or the PC is locked, the camera is released and its light goes off.
- **Light on resources.** It checks about 4 frames per second while no hand is visible and about 15 per second while one is. That works out to roughly 0.5% CPU when idle and about 2–3% while tracking.

## Install

Run `VisualCommand-Setup-x.y.z.exe`. It installs for your user only, with no admin prompt, and adds a Start Menu entry. It can also start the app when you sign in. You can change that later in **General → Start with Windows**. Uninstall it from *Settings → Apps*.

## Use

- **Left-click the tray icon**, or launch the app again, to open the window. The tray icon's colour shows the state: green means tracking, grey means off, amber means paused, locked or camera busy.
- **Right-click the tray icon** for:
  - Tracking on/off
  - Camera preview
  - Pause for 10 minutes
  - Open screenshots folder
  - Quit
- **Gestures tab**: pick an action for any gesture. Gestures set to *nothing* cost nothing. **Test** runs the action straight away.
- **Sensitivity tab**: hand detection strictness, hold time, cooldown, pose confidence and frame rates.
- **General tab**:
  - camera choice and the camera's own settings dialog
  - low-light boost (Auto / Always / Off)
  - an optional *safety gesture*, which must be shown before any other gesture works
- **Show preview** opens a live view with the hand skeleton, the detected pose, the lighting state and the processing time. It is not recorded.

Default mappings: 👍 screenshot · ✊ mute/unmute mic · ✌️ lock PC.

All gestures are hand poses: hold the pose for a moment (0.4 s by default) and the action runs once. Lower your hand or change pose before it can run again. Moving gestures such as swipes were removed in 0.1.3 because webcam motion blur made them unreliable.

Screenshots go to `Pictures\VisualCommand`. Settings and a small text log, which records only gesture names, are kept in `%APPDATA%\VisualCommand`.

## Development

```powershell
uv venv -p 3.11 .venv          # MediaPipe needs Python 3.10-3.12
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\python.exe scripts\fetch_model.py      # one-time, ~8 MB model into models/
.venv\Scripts\python.exe -m visualcommand            # run (add --tray, --bench, --verbose)
.venv\Scripts\python.exe -m pytest -q                # tests
```

`--bench` logs fps, processing time, CPU, memory and the number of network connections (always 0) every 10 s.

### Build the installer

Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

The script:
1. downloads the model and draws the icon
2. runs the tests
3. builds the app with PyInstaller into `dist\VisualCommand\`
4. builds the installer with Inno Setup into `installer\Output\VisualCommand-Setup-<version>.exe`

The version comes from `visualcommand/__init__.py`.

### Layout

| Path | What |
|---|---|
| `visualcommand/tracker.py` | Camera thread: adaptive fps, lighting, MediaPipe, preview |
| `visualcommand/features.py` | Per-frame hand features (finger states, pinch, palm centre...) |
| `visualcommand/engine.py` | Hold-time, cooldown, re-arm and safety-gesture logic |
| `visualcommand/gestures/` | Gesture catalogue (plugins) |
| `visualcommand/actions/` | Action catalogue (plugins) |
| `visualcommand/lighting.py` | Lighting classification + gamma/CLAHE boost |
| `visualcommand/settings_ui.py`, `tray.py`, `main.py` | Window, tray icon, app wiring |
| `installer/VisualCommand.iss`, `VisualCommand.spec` | Packaging |

## Adding a gesture

Add a class to any module in `visualcommand/gestures/`. New modules are picked up automatically. It appears in the Gestures tab without any UI changes.

```python
from visualcommand.gestures.base import PoseGesture, register_gesture

@register_gesture
class ThumbLeft(PoseGesture):              # return a 0..1 score every frame
    id, name, icon, order = "Thumb_Left", "Thumb left", "👈", 30
    description = "Fist with the thumb pointing to your left."

    def score(self, f):
        thumb_only = f.extended == (True, False, False, False, False)
        return 0.9 if f.hand and thumb_only and f.landmarks[4][0] < f.landmarks[2][0] else 0.0
```

`f` is a `FrameFeatures` object. It provides:
- `hand`
- `landmarks` (21 x/y points, mirrored so your right is the image's right)
- `extended` (which fingers are out: thumb, index, middle, ring, pinky)
- `pinch`, `palm_center`, `palm_size`, `index_tip`, `index_dir`
- `mp_label` / `mp_score` (MediaPipe's built-in pose)
- `lighting`

You don't need to write debouncing yourself. The engine handles the hold time, cooldown and "release before firing again". Add a test in `tests/test_gestures.py`.

**Trained gestures:** for poses that rules can't capture, train a custom model with MediaPipe Model Maker on your own photos. Then replace `models/gesture_recognizer.task` and register a `PoseGesture` per new label. The existing `builtin_poses.py` shows how to wrap a model label.

## Adding an action

Add a function to any module in `visualcommand/actions/`:

```python
from visualcommand.actions.base import Param, register_action

@register_action("open_url", "Open a website", group="System",
                 params=(Param("url", "URL", "https://example.com"),))
def open_url(ctx, params):
    import os; os.startfile(params["url"])
    return f"Opened {params['url']}"      # shown in the notification
```

Actions run on a background thread with COM initialised. `ctx` is the app; for example, `ctx.pause(minutes=10)`.
