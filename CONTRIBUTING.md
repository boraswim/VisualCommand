# Contributing to VisualCommand

Thanks for helping. Bug reports, fixes, new gestures, new actions and ideas are all welcome. Please
follow the [code of conduct](CODE_OF_CONDUCT.md), and report security problems privately as described
in [SECURITY.md](SECURITY.md), not in an issue.

## Reporting a bug

Open an issue with the **Bug report** form. The most useful details are what you did, what happened,
your Windows version and webcam, and the end of `visualcommand.log` (in `%APPDATA%\VisualCommand`).

**Gesture fired when it shouldn't, or didn't fire when it should?** That's what the trigger log is
for. Every time a gesture triggers an action, VisualCommand writes a small file to
`%APPDATA%\VisualCommand\trigger_logs` (tray menu → **Open trigger logs**). The files hold only
hand-tracking numbers: no images, and no typed commands. Zip the relevant ones and attach them. They
can be replayed against the rules with `scripts/replay_trigger_logs.py`.

Please never attach screenshots or video of the camera view.

## Setting up

VisualCommand is a Windows app in Python 3.11 with [uv](https://docs.astral.sh/uv/):

```
uv venv .venv -p 3.11
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
.venv\Scripts\python.exe scripts\fetch_model.py
```

Run it with `.venv\Scripts\python.exe -m visualcommand` (add `--verbose` for a detailed log, `--bench`
for CPU and frame-rate figures every 10 seconds), and the tests with
`.venv\Scripts\python.exe -m pytest -q`. The README's **Code** table says what each file does.

## How the app is meant to work

A few principles shape every change:

- **Nothing visual is kept.** Camera frames live in memory for one analysis step and are dropped.
  Never save, log or send a frame. `tests/test_privacy.py` fails the build on code that writes images,
  records video or opens network connections.
- **Fully local.** No network access at runtime. The hand model ships with the app.
- **Measure, then change a rule.** Gesture limits come from real recordings, not guesses. Before
  tightening or loosening a rule, record the pose (and everyday hand movement) with
  `scripts/diagnose_false_triggers.py` or `scripts/diagnose_poses.py`, replay it, and put the measured
  ranges in a comment next to the limit. Delete the recording afterwards.
- **False triggers are worse than misses.** A gesture should only count when the hand is clearly shown
  to the camera (see `visualcommand/deliberate.py`). Actions that can't be undone, like shutting down,
  always ask first with a countdown.
- **Light on resources.** It runs all day in the background. Keep the idle path cheap.

## Adding a gesture or an action

Both are plugins. Put a class or function in any module under `visualcommand/gestures/` or
`visualcommand/actions/` and it shows up in the settings window, with no UI changes needed. The README
has short examples. Add a test for every new gesture rule or action.

## Making a change

1. Fork the repository and create a branch.
2. Match the style of the surrounding code: its naming, comment density and idioms.
3. Run the tests, and try the change in the running app (the camera preview shows what each hand
   measures and why a pose doesn't count).
4. Never commit recordings, trigger logs, screenshots of the camera view, the model file or build
   output (`.gitignore` covers the usual places).
5. Open a pull request and fill in its template.

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
