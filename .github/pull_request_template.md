## What this changes

<!-- What does it do, and why? Link the issue if there is one (Fixes #...). -->

## How I tested it

<!-- For a gesture rule: the recording you measured it on and the before/after results
     (e.g. "deliberate 22/22 fire, everyday movement 0 false triggers"). -->

## Checklist

- [ ] Tests pass (`.venv\Scripts\python.exe -m pytest -q`), with a new test for any new rule or action
- [ ] Tried in the running app (the camera preview shows what each hand measures)
- [ ] No camera frames are saved, logged or sent, and no network access is added
- [ ] Gesture limits come with the measured ranges they're based on, in a comment
- [ ] No recordings, trigger logs, camera screenshots, model file or build output included
