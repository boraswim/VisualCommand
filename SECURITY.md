# Security policy

## Supported versions

Security fixes go into the latest release. If you're on an older version, download the newest
installer from the [releases page](https://github.com/boraswim/VisualCommand/releases/latest) and run
it: it updates in place and keeps your settings.

| Version | Supported |
|---|---|
| Latest release | Yes |
| Older releases | No |

## Reporting a vulnerability

Please report security problems privately, not in a public issue:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability** and describe the problem: what's affected, how to reproduce it, and
   what an attacker could do with it.

Only the maintainer sees the report. You can expect a first reply within a week. Once a fix is
released, the report can be published with credit to you, if you'd like.

## What's in scope

VisualCommand uses your webcam and can run commands on your PC, so these are the most useful areas to
report:

- **Camera data:** any way a camera frame could be written to disk, logged, kept in memory longer than
  one analysis step, or sent anywhere.
- **Network access and updates:** the only network code is the update check in
  `visualcommand/updater.py`, which runs only when the user asks (button, or an opt-in daily check). It
  must only contact this repository on GitHub, send nothing about the user, and run an installer only
  after it matches the size and SHA-256 published for the release. Ways to make it download or run
  something else, or to send data, are in scope.
- **Actions:** "Open app / file / command" runs what you type, and power actions shut down, restart or
  sleep the PC. Ways to make an action run something the user didn't set, or to skip the power
  actions' countdown, are in scope.
- **Settings and logs:** `config.json`, `visualcommand.log` and the trigger logs in
  `%APPDATA%\VisualCommand`. Ways to make the app run something by editing these, or to make the
  trigger logs hold more than hand-tracking numbers, are in scope.
- **The installer:** `VisualCommand-Setup-<version>.exe` installs for the current user only and adds a
  sign-in entry when you choose "Start with Windows".

Bugs in the projects VisualCommand builds on (MediaPipe, OpenCV, Python and others) belong with those
projects. Do tell us if VisualCommand uses one of them in an unsafe way.
