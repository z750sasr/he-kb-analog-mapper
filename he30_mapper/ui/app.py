"""Main window assembled from reusable theme, keyboard, and toggle components."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from ..config import config_path, load_config, save_config
from ..constants import ACTION_BY_ID, CONTROLLER_ACTIONS
from ..keyboards import KeyboardRegistry
from ..models import MapperConfig, ServiceEvent
from ..service import MapperService
from .keyboard_view import KeyboardView
from .theme import BG, LINE, MUTED, SURFACE, configure_styles
from .tray import TrayController
from .widgets import ScrollableFrame, ToggleSetting


AUTO_DETECT_LABEL = "Auto detect (recommended)"


class MapperWindow(tk.Tk):
    """Configuration window; the worker remains active when this is hidden."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Hall Analog Mapper")
        self.geometry("1160x860")
        self.minsize(940, 700)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self.config_data = load_config()
        self.registry = KeyboardRegistry()
        self.service = MapperService(self.config_data, registry=self.registry)
        self.tray = TrayController(self)

        self._adapter_labels = {
            adapter.display_name: adapter.adapter_id
            for adapter in self.registry.definitions()
        }
        self._adapter_labels[AUTO_DETECT_LABEL] = "auto"
        self.active_adapter_id = self._initial_adapter_id()
        initial_layout = self.registry.default_layout(self.config_data.preferred_keyboard)
        self.selected_key_id = initial_layout.keys[0].key_id
        self.digital_output_supported = False

        self.status_var = tk.StringVar(value="Stopped")
        self.device_var = tk.StringVar(value="No keyboard detected")
        self.selected_var = tk.StringVar()
        self.action_var = tk.StringVar()
        self.live_var = tk.StringVar(value="No Hall reports yet")
        self.keyboard_choice_var = tk.StringVar(value=self._preferred_label())
        self.deadzone_var = tk.StringVar(value=str(self.config_data.deadzone_raw))
        self.max_raw_var = tk.StringVar(value=str(self.config_data.max_raw))
        self.sensitivity_var = tk.StringVar(value=f"{self.config_data.sensitivity:.2f}")
        self.threshold_var = tk.StringVar(value=f"{self.config_data.digital_threshold:.2f}")
        self.curve_var = tk.StringVar(value=self.config_data.curve)
        self.keyboard_keys_var = tk.BooleanVar(value=self.config_data.keyboard_keys_enabled)
        self.mapping_override_var = tk.BooleanVar(value=self.config_data.gamepad_mapping_override)
        self.auto_start_var = tk.BooleanVar(value=self.config_data.auto_start)
        self.start_minimized_var = tk.BooleanVar(value=self.config_data.start_minimized)

        configure_styles(self)
        self._build_ui(initial_layout)
        self.select_key(self.selected_key_id)
        self._update_output_capability()
        self.tray.start()
        self.after(50, self._poll_service_events)

        if self.config_data.auto_start:
            self.after(250, self.start_mapping)
        if self.config_data.start_minimized and self.tray.available:
            self.after(300, self.withdraw)

    def _initial_adapter_id(self) -> str:
        if self.config_data.preferred_keyboard != "auto":
            if self.registry.adapter_type(self.config_data.preferred_keyboard):
                return self.config_data.preferred_keyboard
        return self.registry.definitions()[0].adapter_id

    def _preferred_label(self) -> str:
        if self.config_data.preferred_keyboard == "auto":
            return AUTO_DETECT_LABEL
        adapter = self.registry.adapter_type(self.config_data.preferred_keyboard)
        return adapter.display_name if adapter else AUTO_DETECT_LABEL

    def _build_ui(self, initial_layout) -> None:
        self._build_header()
        scroller = ScrollableFrame(self)
        scroller.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        content = scroller.content
        content.configure(padding=(6, 4, 6, 24))
        self._build_keyboard_card(content, initial_layout)
        self._build_controls(content)

    def _build_header(self) -> None:
        header = ttk.Frame(self, padding=(24, 17))
        header.pack(fill="x")
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="HALL INPUT", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Hall Analog Mapper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Physical Hall travel → virtual Xbox controller",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        # Keep status and actions in one compact right-hand block. Stacking
        # these two rows prevents long device messages from pushing buttons
        # outside the window on smaller or high-DPI laptop displays.
        right_box = ttk.Frame(header)
        right_box.pack(side="right", padx=(16, 0))
        status_box = ttk.Frame(right_box)
        status_box.pack(fill="x")
        self.status_label = ttk.Label(status_box, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.pack(anchor="e")
        ttk.Label(status_box, textvariable=self.device_var, style="Muted.TLabel").pack(anchor="e", pady=(3, 0))

        actions = ttk.Frame(right_box)
        actions.pack(anchor="e", pady=(8, 0))
        self.start_button = ttk.Button(
            actions,
            text="Start",
            style="Primary.TButton",
            command=self.start_mapping,
        )
        self.start_button.pack(side="left", padx=4)
        ttk.Button(actions, text="Stop", command=self.stop_mapping).pack(side="left", padx=4)
        ttk.Button(actions, text="Hide", command=self.hide_to_tray).pack(side="left", padx=(10, 0))

    def _build_keyboard_card(self, parent, initial_layout) -> None:
        card = ttk.Frame(parent, style="Surface.TFrame", padding=18)
        card.pack(fill="x")
        heading = ttk.Frame(card, style="Surface.TFrame")
        heading.pack(fill="x", pady=(0, 12))
        heading_text = ttk.Frame(heading, style="Surface.TFrame")
        heading_text.pack(side="left", fill="x", expand=True)
        ttk.Label(heading_text, text="Physical keyboard", style="SurfaceHeading.TLabel").pack(anchor="w")
        ttk.Label(
            heading_text,
            text="Controller output is shown first; the physical legend stays below it, matching the web driver.",
            style="SurfaceMuted.TLabel",
            wraplength=480,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

        choice_box = ttk.Frame(heading, style="Surface.TFrame")
        choice_box.pack(side="right")
        ttk.Label(choice_box, text="DEVICE ADAPTER", style="SurfaceMuted.TLabel").pack(anchor="w")
        self.keyboard_choice = ttk.Combobox(
            choice_box,
            state="readonly",
            width=29,
            textvariable=self.keyboard_choice_var,
            values=[AUTO_DETECT_LABEL, *sorted(self._adapter_labels.keys() - {AUTO_DETECT_LABEL})],
        )
        self.keyboard_choice.pack(pady=(4, 0))
        self.keyboard_choice.bind("<<ComboboxSelected>>", self._keyboard_preference_changed)

        self.keyboard_view = KeyboardView(card, initial_layout, self.select_key)
        self.keyboard_view.pack(fill="x")
        self.keyboard_view.set_mappings(self._mappings())

    def _build_controls(self, parent) -> None:
        controls = ttk.Frame(parent, style="Surface.TFrame")
        controls.pack(fill="both", expand=True, pady=(14, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        mapping = ttk.Frame(controls, style="Surface.TFrame", padding=18)
        mapping.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._build_mapping_panel(mapping)

        tabs = ttk.Notebook(controls)
        tabs.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        response = ttk.Frame(tabs, style="Surface.TFrame", padding=18)
        output = ttk.Frame(tabs, style="Surface.TFrame", padding=18)
        tabs.add(response, text="Response")
        tabs.add(output, text="Keyboard output")
        self._build_response_panel(response)
        self._build_output_panel(output)

    def _build_mapping_panel(self, panel) -> None:
        ttk.Label(panel, text="SELECTED KEY", style="SurfaceMuted.TLabel").pack(anchor="w")
        ttk.Label(panel, textvariable=self.selected_var, style="SurfaceSelected.TLabel").pack(
            anchor="w",
            pady=(3, 14),
        )
        ttk.Label(panel, text="Controller output", style="SurfaceMuted.TLabel").pack(anchor="w")
        self.action_combo = ttk.Combobox(
            panel,
            state="readonly",
            textvariable=self.action_var,
            values=[action.label for action in CONTROLLER_ACTIONS],
        )
        self.action_combo.pack(fill="x", pady=(5, 10))
        self.action_combo.bind("<<ComboboxSelected>>", self._mapping_changed)
        ttk.Button(panel, text="Clear this mapping", command=self.clear_mapping).pack(anchor="w")
        ttk.Separator(panel).pack(fill="x", pady=17)
        ttk.Label(panel, text="Live pressure", style="SurfaceMuted.TLabel").pack(anchor="w")
        self.live_bar = ttk.Progressbar(panel, maximum=100)
        self.live_bar.pack(fill="x", pady=(7, 4))
        ttk.Label(panel, textvariable=self.live_var, style="Surface.TLabel").pack(anchor="w")

    def _build_response_panel(self, panel) -> None:
        ttk.Label(panel, text="Response settings", style="SurfaceHeading.TLabel").grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 12),
        )
        self._setting_row(panel, 1, "Raw deadzone", self.deadzone_var)
        self._setting_row(panel, 2, "Raw full travel", self.max_raw_var)
        self._setting_row(panel, 3, "Sensitivity", self.sensitivity_var)
        self._setting_row(panel, 4, "Button threshold", self.threshold_var)
        ttk.Label(panel, text="Response curve", style="SurfaceMuted.TLabel").grid(
            row=5,
            column=0,
            sticky="w",
            pady=6,
        )
        ttk.Combobox(
            panel,
            state="readonly",
            textvariable=self.curve_var,
            values=("linear", "gentle", "s_curve", "fast"),
            width=16,
        ).grid(row=5, column=1, sticky="ew", pady=6)
        ttk.Checkbutton(
            panel,
            text="Start mapping when the app opens",
            variable=self.auto_start_var,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 3))
        ttk.Checkbutton(
            panel,
            text="Open minimized to the tray",
            variable=self.start_minimized_var,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Button(
            panel,
            text="Save settings",
            style="Primary.TButton",
            command=self.save_settings,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Label(
            panel,
            text=f"Config: {config_path()}",
            style="SurfaceMuted.TLabel",
            wraplength=320,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 0))
        panel.columnconfigure(1, weight=1)

    def _build_output_panel(self, panel) -> None:
        ttk.Label(panel, text="Digital keyboard output", style="SurfaceHeading.TLabel").pack(anchor="w")
        ttk.Label(
            panel,
            text="These controls follow Wootility's gamepad-mode semantics and are applied by the selected device adapter.",
            style="SurfaceMuted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(4, 16))

        self.keyboard_keys_setting = ToggleSetting(
            panel,
            title="Enable keyboard keys",
            description=(
                "Enable digital keys if you want ordinary typing output. Disable them to prevent "
                "keyboard events from interfering with controller output."
            ),
            variable=self.keyboard_keys_var,
            command=self._output_policy_changed,
        )
        self.keyboard_keys_setting.pack(fill="x")
        ttk.Separator(panel).pack(fill="x", pady=17)
        self.mapping_override_setting = ToggleSetting(
            panel,
            title="Gamepad mapping override",
            description="Disable keyboard input only on physical keys that have gamepad bindings.",
            variable=self.mapping_override_var,
            command=self._output_policy_changed,
        )
        self.mapping_override_setting.pack(fill="x")

    @staticmethod
    def _setting_row(parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, style="SurfaceMuted.TLabel").grid(
            row=row,
            column=0,
            sticky="w",
            pady=6,
        )
        ttk.Entry(parent, textvariable=variable, width=18).grid(
            row=row,
            column=1,
            sticky="ew",
            pady=6,
        )

    def _mappings(self) -> dict[str, str]:
        return self.config_data.mappings_for(self.active_adapter_id)

    def _keyboard_preference_changed(self, _event=None) -> None:
        preferred = self._adapter_labels.get(self.keyboard_choice_var.get(), "auto")
        self.config_data.preferred_keyboard = preferred
        if preferred != "auto":
            adapter = self.registry.adapter_type(preferred)
            if adapter:
                self.active_adapter_id = adapter.adapter_id
                self.keyboard_view.set_layout(adapter.layout)
                self.keyboard_view.set_mappings(self._mappings())
                self.select_key(adapter.layout.keys[0].key_id)
        save_config(self.config_data)
        self.service.update_config(self.config_data)
        if self.service.running:
            self.set_status("Adapter preference will take effect after Stop → Start")

    def select_key(self, key_id: int) -> None:
        key = self.keyboard_view.layout.by_id.get(key_id)
        if key is None:
            return
        self.selected_key_id = key_id
        self.keyboard_view.select(key_id)
        self.selected_var.set(f"{key.label}  ·  physical slot {key_id}")
        action = ACTION_BY_ID.get(self._mappings().get(str(key_id), "none"), ACTION_BY_ID["none"])
        self.action_var.set(action.label)

    def _mapping_changed(self, _event: Any = None) -> None:
        chosen = next(
            (action for action in CONTROLLER_ACTIONS if action.label == self.action_var.get()),
            ACTION_BY_ID["none"],
        )
        mappings = self._mappings()
        if chosen.value == "none":
            mappings.pop(str(self.selected_key_id), None)
        else:
            mappings[str(self.selected_key_id)] = chosen.value
        self._publish_config()
        self.keyboard_view.set_mappings(mappings)

    def clear_mapping(self) -> None:
        mappings = self._mappings()
        mappings.pop(str(self.selected_key_id), None)
        self.action_var.set(ACTION_BY_ID["none"].label)
        self._publish_config()
        self.keyboard_view.set_mappings(mappings)

    def _publish_config(self) -> None:
        self.config_data.sanitize()
        save_config(self.config_data)
        self.service.update_config(self.config_data)

    def _output_policy_changed(self) -> None:
        if not self.keyboard_keys_var.get() and self.digital_output_supported:
            confirmed = messagebox.askyesno(
                "Disable keyboard typing?",
                "This adapter will stop this keyboard from typing while mapping is active. "
                "Keep another input method available. Continue?",
                parent=self,
            )
            if not confirmed:
                self.keyboard_keys_var.set(True)
                return
        self.config_data.keyboard_keys_enabled = self.keyboard_keys_var.get()
        self.config_data.gamepad_mapping_override = self.mapping_override_var.get()
        self.mapping_override_setting.switch.set_enabled(self.keyboard_keys_var.get())
        self._publish_config()
        if not self.digital_output_supported:
            self.set_status("Policy saved; the current adapter cannot apply digital-key suppression", error=True)

    def _update_output_capability(self, message: str = "") -> None:
        if self.digital_output_supported:
            note = message or "Supported by the detected keyboard adapter."
            self.keyboard_keys_setting.set_note(note)
            self.mapping_override_setting.set_note(note)
        else:
            note = message or (
                "Saved as a preference, but this adapter cannot safely change the keyboard's "
                "digital output. Controller mapping still works."
            )
            self.keyboard_keys_setting.set_note(note, error=True)
            self.mapping_override_setting.set_note(note, error=True)
        self.mapping_override_setting.switch.set_enabled(self.keyboard_keys_var.get())

    def save_settings(self, silent: bool = False) -> bool:
        try:
            self.config_data.deadzone_raw = int(self.deadzone_var.get())
            self.config_data.max_raw = int(self.max_raw_var.get())
            self.config_data.sensitivity = float(self.sensitivity_var.get())
            self.config_data.digital_threshold = float(self.threshold_var.get())
            self.config_data.curve = self.curve_var.get()
            self.config_data.keyboard_keys_enabled = self.keyboard_keys_var.get()
            self.config_data.gamepad_mapping_override = self.mapping_override_var.get()
            self.config_data.auto_start = self.auto_start_var.get()
            self.config_data.start_minimized = self.start_minimized_var.get()
            self._publish_config()
            if not silent:
                self.set_status("Settings saved")
            return True
        except ValueError:
            messagebox.showerror(
                "Invalid settings",
                "Deadzone/full travel must be integers; sensitivity and threshold must be numbers.",
                parent=self,
            )
            return False

    def start_mapping(self) -> None:
        if not self.save_settings(silent=True):
            return
        self.service.start()
        self.start_button.configure(state="disabled")

    def stop_mapping(self) -> None:
        self.service.stop()
        self.start_button.configure(state="normal")
        self.set_status("Mapping stopped")
        self.tray.update(False, "Hall Analog Mapper · stopped")

    def set_status(self, message: str, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="Error.Status.TLabel" if error else "Status.TLabel")

    def _poll_service_events(self) -> None:
        try:
            while True:
                self._handle_service_event(self.service.events.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll_service_events)

    def _handle_service_event(self, event: ServiceEvent) -> None:
        if event.kind == "travel" and event.physical_index is not None and event.value is not None:
            value = max(0.0, min(1.0, event.value))
            self.keyboard_view.set_travel(event.physical_index, value)
            if event.physical_index == self.selected_key_id:
                self.live_bar["value"] = value * 100
                raw = f" · raw {event.raw_value}" if event.raw_value is not None else ""
                self.live_var.set(f"{value * 100:.1f}%{raw}")
            return

        if event.kind in {"detected", "connected"} and event.keyboard_id:
            adapter = self.registry.adapter_type(event.keyboard_id)
            if adapter:
                self.active_adapter_id = event.keyboard_id
                self.keyboard_view.set_layout(adapter.layout)
                self.keyboard_view.set_mappings(self._mappings())
                self.select_key(adapter.layout.keys[0].key_id)
            display_name = event.keyboard_name or (
                adapter.display_name if adapter else event.keyboard_id
            )
            self.device_var.set(display_name)
            self.digital_output_supported = bool(event.digital_output_supported)
            self._update_output_capability()

        if event.kind == "connected":
            self.set_status(event.message)
            self.tray.update(True, event.message)
        elif event.kind == "policy":
            self.digital_output_supported = bool(event.digital_output_supported)
            self._update_output_capability(event.message)
        elif event.kind in {"error", "disconnected"}:
            self.set_status(event.message, error=True)
            self.tray.update(False, "Hall Analog Mapper · disconnected")
            if event.kind == "error":
                self.start_button.configure(state="normal")
        elif event.message:
            self.set_status(event.message)

    def hide_to_tray(self) -> None:
        if self.tray.available:
            self.withdraw()
        else:
            self.iconify()

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def exit_application(self) -> None:
        self.service.stop()
        self.tray.stop()
        self.destroy()


def run_app() -> None:
    app = MapperWindow()
    app.mainloop()
