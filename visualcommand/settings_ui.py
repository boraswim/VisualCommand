"""The app window: gesture → action mapping, general options, sensitivity, privacy.

Everything is built from the gesture and action registries, so new gestures or
actions show up here without UI changes. Changes apply and save immediately.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from visualcommand import APP_NAME, __version__, actions, gestures, sound, winutil
from visualcommand.config import DEFAULTS
from visualcommand.icon import make_icon

NOTHING = "— nothing —"
ACTION_INDENT = "      "
HEADER_MARK = "▸ "


def header_item(group: str) -> str:
    """Dropdown line for a category (not selectable)."""
    return f"{HEADER_MARK}{group.upper()}"


def is_header(item: str) -> bool:
    return item.startswith(HEADER_MARK)


def order_gestures(catalogue: list, mappings: dict) -> tuple[list, list]:
    """Split gestures into (assigned, unassigned), each keeping catalogue order."""
    assigned = [g for g in catalogue if (mappings.get(g.id) or {}).get("action")]
    unassigned = [g for g in catalogue if g not in assigned]
    return assigned, unassigned
LIGHTING_MODES = {"Auto (only when needed)": "auto", "Always": "always", "Off": "off"}

PRIVACY_TEXT = (
    "VisualCommand runs entirely on this PC.\n\n"
    "•  Camera frames are analysed in memory and dropped straight away. They are never "
    "saved, logged or sent anywhere, and the camera preview is not recorded.\n"
    "•  The hand-tracking model is bundled with the app and loaded from disk. The app only "
    "goes online when you check for updates (the button in General, or the once-a-day check "
    "if you turn it on): it asks GitHub for the latest release and, if you choose to update, "
    "downloads the installer. Nothing about you or your gestures is sent.\n"
    "•  When tracking is off, paused or the PC is locked, the camera is released and its "
    "light goes off.\n"
    "•  The only files written are your settings (config.json), a small text log of "
    "which gestures fired, and (if turned on in General) a trigger log, all in "
    "%APPDATA%\\VisualCommand, plus the screenshots you ask for in Pictures\\VisualCommand.\n"
    "•  The trigger log holds only hand-tracking numbers (21 hand points, scores, settings, "
    "which action ran) for the moments a gesture fired, never images. Each record is "
    "deleted after 24 hours and nothing is ever sent anywhere."
)


class SettingsWindow:
    def __init__(self, root: tk.Tk, app) -> None:
        self.root = root
        self.app = app
        self.cfg = app.cfg
        self._save_job = None

        root.title(APP_NAME)
        root.geometry("820x640")
        root.minsize(680, 480)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        self._icon = ImageTk.PhotoImage(make_icon("on", 64))
        root.iconphoto(True, self._icon)

        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 14))
        style.configure("Name.TLabel", font=("Segoe UI Semibold", 10))
        style.configure("Desc.TLabel", foreground="#666666", font=("Segoe UI", 9))
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 11))
        style.configure("Status.TLabel", foreground="#444444", font=("Segoe UI", 9))

        self._actions = actions.catalogue()
        self._action_by_id = {a.id: a for a in self._actions}
        self._action_by_name = {a.name: a for a in self._actions}
        # Dropdown entries grouped by category: a header line, then its actions indented.
        self._action_items: list[str] = [NOTHING]
        self._action_by_item: dict[str, object] = {}
        self._item_by_id: dict[str, str] = {}
        group = None
        for a in self._actions:
            if a.group != group:
                group = a.group
                self._action_items.append(header_item(group))
            item = ACTION_INDENT + a.name
            self._action_items.append(item)
            self._action_by_item[item] = a
            self._item_by_id[a.id] = item

        self._build_header()
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=12, pady=(4, 0))
        nb.add(self._build_gestures(nb), text="  Gestures  ")
        nb.add(self._build_general(nb), text="  General  ")
        nb.add(self._build_sensitivity(nb), text="  Sensitivity  ")
        nb.add(self._build_privacy(nb), text="  Privacy  ")

        self.status = ttk.Label(root, style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", padx=14, pady=8)
        self.refresh_status()

    # --- window -----------------------------------------------------------------------
    def show(self) -> None:
        self._populate_gestures()      # re-sort: newly assigned gestures move to the top
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.autostart_var.set(winutil.autostart_enabled())
        self.refresh_status()

    def hide(self) -> None:
        self.root.withdraw()

    # --- header -----------------------------------------------------------------------
    def _build_header(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(bar, text=APP_NAME, style="Title.TLabel").pack(side="left")
        self.track_btn = ttk.Button(bar, width=18, command=self._toggle_tracking)
        self.track_btn.pack(side="right")
        self.preview_btn = ttk.Button(bar, width=16, command=self.app.toggle_preview)
        self.preview_btn.pack(side="right", padx=6)

    def _toggle_tracking(self) -> None:
        self.app.set_tracking(not self.cfg.get("tracking_enabled", True))

    def refresh_status(self) -> None:
        tr = self.app.tracker
        on = self.cfg.get("tracking_enabled", True)
        self.track_btn.configure(text="■  Turn tracking off" if on else "▶  Turn tracking on")
        self.preview_btn.configure(text="Hide preview" if tr.preview else "Show preview")
        parts = [f"Tracking: {tr.status}"]
        if self.app.is_paused():
            parts[0] = "Tracking: paused"
        if tr.status == "running":
            parts.append(f"Lighting: {tr.lighting}")
        if self.app.last_event:
            parts.append(f"Last: {self.app.last_event}")
        self.status.configure(text="   ·   ".join(parts))

    # --- scrolling tab content ----------------------------------------------------------
    @staticmethod
    def _scrollable(parent, padding) -> tuple[ttk.Frame, ttk.Frame, tk.Canvas]:
        """(outer frame for the notebook, inner frame to fill, its canvas).

        Tabs scroll when their content is taller than the window (small screens).
        """
        outer = ttk.Frame(parent)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas, padding=padding)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def on_wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return outer, body, canvas

    # --- gestures tab -----------------------------------------------------------------
    def _build_gestures(self, parent) -> ttk.Frame:
        outer, body, canvas = self._scrollable(parent, (12, 8))
        body.columnconfigure(1, weight=1)
        self._gesture_body = body
        self._gesture_canvas = canvas
        self._populate_gestures()
        return outer

    def _populate_gestures(self, focus_gid: str | None = None) -> None:
        """(Re)build the gesture rows: assigned ones first, then the rest.

        Runs when the window opens and whenever a gesture gets or loses its action.
        With `focus_gid`, the list scrolls to that gesture (and focuses its command
        field if it still needs one) instead of jumping back to the top.
        """
        body = self._gesture_body
        self.root.focus_set()          # lets a half-typed command field save (FocusOut)
        for child in body.winfo_children():
            child.destroy()
        self._rows: dict[str, dict] = {}
        mappings = self.cfg.mappings()
        assigned, unassigned = order_gestures(gestures.catalogue(), mappings)
        row = 0
        for title, group in (("In use", assigned), ("Not assigned", unassigned)):
            if not group:
                continue
            ttk.Label(body, text=title, style="Section.TLabel").grid(
                row=row, column=0, columnspan=4, sticky="w", pady=(10 if row else 0, 4))
            row += 1
            for g in group:
                self._gesture_row(body, row, g, self._action_items, mappings.get(g.id))
                row += 2
        canvas = self._gesture_canvas
        target = self._rows.get(focus_gid) if focus_gid else None
        if target is None:
            canvas.yview_moveto(0)
            return
        body.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        total = max(1, body.winfo_height())
        y = target["anchor"].winfo_y()
        visible = canvas.winfo_height() / total
        # put the moved gesture about a third of the way down the visible area
        canvas.yview_moveto(max(0.0, y / total - visible / 3))
        if target["needs_param"]():
            target["param"].focus_set()

    def _gesture_row(self, body, row, g, action_names, mapping) -> None:
        ttk.Label(body, text=g.icon, font=("Segoe UI Emoji", 16), width=3).grid(
            row=row, column=0, rowspan=2, sticky="w")
        ttk.Label(body, text=g.name, style="Name.TLabel").grid(row=row, column=1, sticky="w")
        # wrap so long descriptions don't run under the action dropdown
        ttk.Label(body, text=g.description, style="Desc.TLabel", wraplength=420).grid(
            row=row + 1, column=1, sticky="w", pady=(0, 6))

        var = tk.StringVar()
        combo = ttk.Combobox(body, textvariable=var, values=action_names, state="readonly", width=30,
                             height=min(len(action_names), 26))
        combo.grid(row=row, column=2, sticky="e", padx=6)
        param_var = tk.StringVar()
        param = ttk.Entry(body, textvariable=param_var, width=33)
        test = ttk.Button(body, text="Test", width=6)
        test.grid(row=row, column=3, sticky="e")

        spec = self._action_by_id.get((mapping or {}).get("action", ""))
        # The closed box shows the plain action name; the open list is indented by category.
        var.set(spec.name if spec else NOTHING)
        last_valid = [var.get()]
        if spec and spec.params:
            param_var.set((mapping.get("params") or {}).get(spec.params[0].key, ""))

        def current():
            return self._action_by_name.get(var.get())

        def show_param():
            spec = current()
            if spec and spec.params:
                param.grid(row=row + 1, column=2, sticky="e", padx=6, pady=(0, 6))
            else:
                param.grid_remove()
            test.state(["!disabled"] if spec else ["disabled"])

        def save(*_):
            spec = current()
            params = {spec.params[0].key: param_var.get().strip()} if spec and spec.params else {}
            self.cfg.set_mapping(g.id, spec.id if spec else "", params)

        def on_select(_):
            item = var.get()
            if is_header(item):               # category headers can't be picked
                var.set(last_valid[0])
                return
            picked = self._action_by_item.get(item)
            was_assigned = last_valid[0] != NOTHING
            var.set(picked.name if picked else NOTHING)
            last_valid[0] = var.get()
            show_param()
            save()
            if (picked is not None) != was_assigned:
                # Moved between "In use" and "Not assigned": re-sort now (after this
                # event, since the rebuild destroys this combobox) and keep it in view.
                self.root.after_idle(lambda: self._populate_gestures(focus_gid=g.id))
                return
            if current() and current().params and not param_var.get():
                param.focus_set()

        def do_test():
            spec = current()
            if spec:
                params = {spec.params[0].key: param_var.get().strip()} if spec.params else {}
                self.app.test_action(spec.id, params)

        combo.bind("<<ComboboxSelected>>", on_select)
        param.bind("<FocusOut>", save)
        param.bind("<Return>", save)
        test.configure(command=do_test)
        show_param()
        self._rows[g.id] = {"anchor": combo, "param": param,
                            "needs_param": lambda: bool(current() and current().params
                                                        and not param_var.get())}

    # --- general tab ------------------------------------------------------------------
    def _build_general(self, parent) -> ttk.Frame:
        outer, f, _canvas = self._scrollable(parent, 16)
        f.columnconfigure(1, weight=1)
        self._general_outer = outer
        r = 0

        self.autostart_var = tk.BooleanVar(value=winutil.autostart_enabled())
        ttk.Checkbutton(f, text="Start VisualCommand when I sign in to Windows",
                        variable=self.autostart_var,
                        command=lambda: winutil.set_autostart(self.autostart_var.get())
                        ).grid(row=r, column=0, columnspan=3, sticky="w", pady=4)
        r += 1

        notif = tk.BooleanVar(value=self.cfg.get("notifications", True))
        ttk.Checkbutton(f, text="Show a popup when a gesture runs an action", variable=notif,
                        command=lambda: self.cfg.set("notifications", notif.get())
                        ).grid(row=r, column=0, columnspan=3, sticky="w", pady=4)
        r += 1

        snd = tk.BooleanVar(value=self.cfg.get("sounds", True))

        def on_sound():
            self.cfg.set("sounds", snd.get())
            if snd.get():
                sound.play("action")   # let the user hear what they turned on
        ttk.Checkbutton(f, text="Play a sound when a gesture runs an action", variable=snd,
                        command=on_sound).grid(row=r, column=0, columnspan=3, sticky="w", pady=4)
        r += 1

        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1

        ttk.Label(f, text="Camera").grid(row=r, column=0, sticky="w", pady=4)
        cams = [f"Camera {i}" + (" (default)" if i == 0 else "") for i in range(5)]
        cam = ttk.Combobox(f, values=cams, state="readonly", width=22)
        cam.current(min(int(self.cfg.get("camera_index", 0)), 4))
        cam.grid(row=r, column=1, sticky="w")

        def on_cam(_):
            self.cfg.set("camera_index", cam.current())
            self.app.tracker.wake()
        cam.bind("<<ComboboxSelected>>", on_cam)
        ttk.Button(f, text="Camera settings…", command=self.app.tracker.request_camera_settings
                   ).grid(row=r, column=2, sticky="e")
        r += 1
        ttk.Label(f, text="Use the camera's own settings to raise exposure or brightness if your "
                          "room is dark. Tracking must be on.", style="Desc.TLabel"
                  ).grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Label(f, text="Left / right hand").grid(row=r, column=0, sticky="w", pady=(10, 4))
        orient_msg = ttk.Label(f, style="Desc.TLabel", wraplength=420,
                               text="Some cameras already mirror their picture. If gestures work "
                                    "with one hand but not the other, check this.")
        orient_msg.grid(row=r + 1, column=1, columnspan=2, sticky="w")

        def check_orientation():
            if not self.cfg.get("tracking_enabled", True) or self.app.is_paused():
                self.app.set_tracking(True)
            orient_btn.state(["disabled"])
            orient_msg.configure(text="Raise your RIGHT hand, open, in front of the camera now "
                                      "(about 4 seconds). Keep your left hand out of view.")

            def done(message, ok):
                def show():
                    orient_btn.state(["!disabled"])
                    orient_msg.configure(text=message)
                self.app.post(show)
                self.app.notify(message, title="Camera orientation", error=not ok)
            self.app.tracker.check_orientation(done)

        orient_btn = ttk.Button(f, text="Check camera orientation…", command=check_orientation)
        orient_btn.grid(row=r, column=1, sticky="w", pady=(10, 4))
        r += 2

        ttk.Label(f, text="Low-light boost").grid(row=r, column=0, sticky="w", pady=(10, 4))
        light = ttk.Combobox(f, values=list(LIGHTING_MODES), state="readonly", width=26)
        mode = self.cfg.get("lighting_mode", "auto")
        light.set(next((k for k, v in LIGHTING_MODES.items() if v == mode), "Auto (only when needed)"))
        light.grid(row=r, column=1, sticky="w", pady=(10, 4))
        light.bind("<<ComboboxSelected>>",
                   lambda _: self.cfg.set("lighting_mode", LIGHTING_MODES[light.get()]))
        r += 1
        ttk.Label(f, text="Brightens dark or backlit frames in memory before hand tracking.",
                  style="Desc.TLabel").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1

        poses = gestures.catalogue()
        names = ["Off"] + [g.name for g in poses]
        by_name = {g.name: g.id for g in poses}
        ttk.Label(f, text="Safety gesture").grid(row=r, column=0, sticky="w", pady=4)
        arm = ttk.Combobox(f, values=names, state="readonly", width=22)
        cur = self.cfg.get("arm_gesture", "")
        arm.set(next((g.name for g in poses if g.id == cur), "Off"))
        arm.grid(row=r, column=1, sticky="w")
        arm.bind("<<ComboboxSelected>>",
                 lambda _: self.cfg.set("arm_gesture", by_name.get(arm.get(), "")))
        r += 1
        ttk.Label(f, text="If set, other gestures only work for a few seconds after you show this "
                          "one. Use it if gestures fire by accident.", style="Desc.TLabel"
                  ).grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1
        ttk.Label(f, text="Trigger log").grid(row=r, column=0, sticky="w", pady=4)
        tlog = tk.BooleanVar(value=self.cfg.get("trigger_log", True))
        ttk.Checkbutton(f, text="Keep a 24-hour log of triggered gestures", variable=tlog,
                        command=lambda: self.cfg.set("trigger_log", tlog.get())
                        ).grid(row=r, column=1, sticky="w")
        ttk.Button(f, text="Open logs folder", command=self.app.open_trigger_logs
                   ).grid(row=r, column=2, sticky="e")
        r += 1
        ttk.Label(f, text="Hand-tracking numbers only, never images. Each record is deleted after "
                          "24 hours. Nothing is sent anywhere; you can share the folder to help "
                          "tune false triggers.", style="Desc.TLabel", wraplength=520
                  ).grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=12)
        r += 1
        ttk.Label(f, text="Updates").grid(row=r, column=0, sticky="w", pady=4)
        self.update_msg = ttk.Label(f, text=f"You have version {__version__}.")
        self.update_msg.grid(row=r, column=1, sticky="w")
        self.update_btn = ttk.Button(f, text="Check for updates", command=self._update_clicked)
        self.update_btn.grid(row=r, column=2, sticky="e")
        r += 1
        auto = tk.BooleanVar(value=self.cfg.get("auto_update_check", False))
        ttk.Checkbutton(f, text="Check automatically once a day", variable=auto,
                        command=lambda: self.cfg.set("auto_update_check", auto.get())
                        ).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(f, text="Checking asks GitHub for the latest release; it's the only time the app "
                          "goes online, and nothing about you is sent. Updating downloads the "
                          "installer, checks it's the published file, and restarts the app.",
                  style="Desc.TLabel", wraplength=520).grid(row=r, column=1, columnspan=2, sticky="w")
        return outer

    def _update_clicked(self) -> None:
        if self.app.update_state.get("status") == "available":
            self.app.start_update()
        else:
            self.app.check_for_updates(manual=True)

    def refresh_update(self) -> None:
        """Show the update check / download state (called on the Tk thread)."""
        st = self.app.update_state
        status = st.get("status", "idle")
        self.update_msg.configure(text=st.get("message") or f"You have version {__version__}.")
        busy = status in ("checking", "downloading", "installing")
        self.update_btn.configure(text="Update now" if status == "available" else "Check for updates")
        self.update_btn.state(["disabled"] if busy else ["!disabled"])

    # --- sensitivity tab ----------------------------------------------------------------
    def _build_sensitivity(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        f.columnconfigure(1, weight=1)
        sens = self.cfg.sensitivity()
        self._scales: list = []

        def slider(row, label, key, lo, hi, fmt, help_text, top=False, integer=True):
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", pady=(8, 0))
            value_lbl = ttk.Label(f, width=8)
            value_lbl.grid(row=row, column=2, sticky="e")
            if top:
                getter = lambda: self.cfg.get(key)
            else:
                getter = lambda: self.cfg.sensitivity()[key]
            var = tk.DoubleVar(value=getter())

            def changed(_=None):
                v = round(var.get(), 2)
                value_lbl.configure(text=fmt.format(v))
                if top:
                    self.cfg.data[key] = int(round(v)) if integer else v
                else:
                    self.cfg.data["sensitivity"][key] = v
                self._save_later()

            ttk.Scale(f, from_=lo, to=hi, variable=var, command=changed).grid(
                row=row, column=1, sticky="ew", padx=10, pady=(8, 0))
            ttk.Label(f, text=help_text, style="Desc.TLabel", wraplength=540).grid(
                row=row + 1, column=1, sticky="w")
            changed()
            self._scales.append((var, key, top, changed))

        slider(0, "Hand detection strictness", "hand_strictness", 0.3, 0.9, "{:.2f}",
               "Raise if shadows or clothing get detected as hands; lower if real hands are "
               "missed in dim light.", top=True, integer=False)
        slider(2, "Hold time", "hold_time", 0.2, 1.5, "{:.2f} s",
               "How long a pose must be held before it fires.")
        slider(4, "Cooldown", "cooldown", 0.5, 5.0, "{:.1f} s",
               "Minimum time before the same gesture can fire again.")
        slider(6, "Pose confidence", "min_score", 0.4, 0.95, "{:.2f}",
               "Higher = fewer accidental triggers, but poses must be clearer.")
        slider(8, "Gesture zone", "gesture_zone", 0.35, 0.9, "top {:.0%}",
               "Hand must be raised into this top part of the view. Bigger if real gestures "
               "are missed, smaller if a resting hand triggers.")
        ttk.Separator(f).grid(row=10, column=0, columnspan=3, sticky="ew", pady=12)
        slider(11, "Idle checks / second", "idle_fps", 1, 10, "{:.0f}",
               "When no hand is visible. Lower uses less CPU but reacts later.", top=True)
        slider(13, "Tracking frames / second", "active_fps", 5, 30, "{:.0f}",
               "While a hand is visible. Higher reacts faster but uses more CPU.", top=True)

        def reset():
            for var, key, top, changed in self._scales:
                var.set(DEFAULTS[key] if top else DEFAULTS["sensitivity"][key])
                changed()   # Scale doesn't call its command for programmatic changes

        ttk.Button(f, text="Reset to defaults", command=reset).grid(
            row=15, column=0, sticky="w", pady=16)
        return f

    def _save_later(self) -> None:
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(600, self.cfg.save)

    # --- privacy tab --------------------------------------------------------------------
    def _build_privacy(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=16)
        ttk.Label(f, text=PRIVACY_TEXT, wraplength=700, justify="left").pack(anchor="w")
        ttk.Label(f, text=f"\n{APP_NAME} {__version__}", style="Desc.TLabel").pack(anchor="w")
        return f
