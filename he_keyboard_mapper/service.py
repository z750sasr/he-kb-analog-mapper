"""Brand-independent background keyboard-to-controller service."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from .controller import ControllerOutput, MappingEngine, VirtualXboxController
from .keyboards import (
    DigitalOutputPolicy,
    KeyboardRegistry,
    KeyTravelEvent,
    LayerChangeEvent,
    TravelCalibration,
)
from .models import MapperConfig, ServiceEvent


class _KeyboardControllerSession:
    """One physical keyboard feeding one virtual Xbox controller."""

    def __init__(
        self,
        selection_id: str,
        service: "MapperService",
    ) -> None:
        self.selection_id = selection_id
        self.service = service
        self.stop_requested = threading.Event()
        self.thread = threading.Thread(
            target=self._run,
            name=f"Hall mapper {selection_id}",
            daemon=True,
        )

    @property
    def alive(self) -> bool:
        return self.thread.is_alive()

    def start(self) -> None:
        self.thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self.stop_requested.set()
        if self.thread is not threading.current_thread():
            self.thread.join(timeout)

    def _config_for_device(self, device_id: str) -> tuple[MapperConfig, int]:
        config, revision = self.service._config_snapshot()
        config = MapperConfig.from_dict(config.to_dict())
        config.apply_settings_for(device_id)
        return config, revision

    def _run(self) -> None:
        adapter = None
        controller: ControllerOutput | None = None
        config_revision = -1
        config = MapperConfig()
        engine = MappingEngine(config)
        identity = None
        settings_id = self.selection_id
        policy_key: tuple[bool, bool, frozenset[int]] | None = None
        connected_at = 0.0
        last_travel_at = 0.0
        no_report_warning_sent = False

        try:
            adapter, identity = self.service.registry.connect(self.selection_id)
            settings_id = identity.settings_id
            config, config_revision = self._config_for_device(settings_id)
            engine.update_config(config)
            engine.update_keyboard(settings_id)
            display_name = identity.device_name or identity.model_name
            self.service.events.put(
                ServiceEvent(
                    "detected",
                    f"Detected {display_name}",
                    keyboard_id=identity.adapter_id,
                    keyboard_name=identity.model_name,
                    device_id=settings_id,
                    device_name=identity.device_name,
                    layout_id=identity.layout_id,
                    digital_output_supported=adapter.capabilities.digital_output_policy,
                )
            )

            self.service.events.put(ServiceEvent("preparing", f"Preparing {display_name} Hall telemetry..."))
            adapter.prepare()

            # The virtual controller appears in Windows only after the keyboard
            # has been found and its Hall telemetry is ready.
            controller = self.service._controller_factory()
            policy_key = self.service._policy_key(config, settings_id)
            policy_supported, policy_message = self.service._apply_policy(adapter, config, settings_id)
            self.service.events.put(
                ServiceEvent(
                    "policy",
                    policy_message,
                    keyboard_id=identity.adapter_id,
                    device_id=settings_id,
                    digital_output_supported=policy_supported,
                )
            )

            self.service._session_connected(settings_id)
            connected_at = time.monotonic()
            last_travel_at = connected_at
            self.service.events.put(
                ServiceEvent(
                    "connected",
                    f"{display_name} connected as controller",
                    keyboard_id=identity.adapter_id,
                    keyboard_name=identity.model_name,
                    device_id=settings_id,
                    device_name=identity.device_name,
                    layout_id=identity.layout_id,
                    digital_output_supported=adapter.capabilities.digital_output_policy,
                )
            )

            while not self.stop_requested.is_set() and not self.service._stop.is_set():
                event = adapter.read_event(100)
                now = time.monotonic()
                next_config, next_revision = self._config_for_device(settings_id)
                if next_revision != config_revision:
                    config, config_revision = next_config, next_revision
                    engine.update_config(config)
                    next_policy_key = self.service._policy_key(config, settings_id)
                    if next_policy_key != policy_key:
                        policy_key = next_policy_key
                        supported, message = self.service._apply_policy(adapter, config, settings_id)
                        self.service.events.put(
                            ServiceEvent(
                                "policy",
                                message,
                                keyboard_id=identity.adapter_id,
                                device_id=settings_id,
                                digital_output_supported=supported,
                            )
                        )

                if isinstance(event, LayerChangeEvent):
                    no_report_warning_sent = True
                    self.service.events.put(
                        ServiceEvent(
                            "profile",
                            f"Profile {event.profile_index + 1}, layer {event.display_layer}",
                            keyboard_id=identity.adapter_id,
                            device_id=settings_id,
                        )
                    )
                    continue
                if not isinstance(event, KeyTravelEvent):
                    if (
                        identity.adapter_id == "epomaker_he30"
                        and not no_report_warning_sent
                        and now - connected_at >= 5.0
                    ):
                        diagnostics = adapter.diagnostics()
                        telemetry = diagnostics.get("telemetry_reports", 0)
                        unresolved = diagnostics.get("unresolved_reports", 0)
                        if telemetry:
                            message = (
                                f"{display_name} is receiving HE30 reports, but {unresolved} could not be matched "
                                "to physical keys. Check the keyboard layer/profile mappings."
                            )
                        else:
                            message = (
                                f"{display_name} is connected, but no HE30 Hall travel reports have arrived yet. "
                                "Press HE30 keys; if this stays visible, replug the HE30 and make sure no web driver "
                                "or older mapper copy is connected to it."
                            )
                        self.service.events.put(
                            ServiceEvent(
                                "diagnostic",
                                message,
                                keyboard_id=identity.adapter_id,
                                device_id=settings_id,
                                device_name=identity.device_name,
                            )
                        )
                        no_report_warning_sent = True
                    continue

                last_travel_at = now
                no_report_warning_sent = True
                calibration = TravelCalibration(config.deadzone_raw, config.max_raw)
                normalized = adapter.normalize_travel(event.raw_value, calibration)
                value, state = engine.update_value(event.key_id, normalized)
                controller.apply(state)
                self.service.events.put(
                    ServiceEvent(
                        "travel",
                        physical_index=event.key_id,
                        value=value,
                        raw_value=event.raw_value,
                        keyboard_id=identity.adapter_id,
                        device_id=settings_id,
                    )
                )
        except Exception as error:
            name = identity.device_name if identity and identity.device_name else self.selection_id
            self.service.events.put(
                ServiceEvent(
                    "disconnected",
                    f"{name}: {error}",
                    keyboard_id=identity.adapter_id if identity else self.selection_id.split(":", 1)[0],
                    device_id=settings_id,
                    device_name=identity.device_name if identity else None,
                )
            )
        finally:
            self.service._session_disconnected(settings_id)
            if controller is not None:
                try:
                    controller.reset()
                except Exception:
                    pass
                try:
                    controller.close()
                except Exception:
                    pass
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:
                    pass


class MapperService:
    """Own auto-detection and one virtual controller per active keyboard.

    Brand-specific code ends at the ``KeyboardAdapter`` interface. That makes
    reconnect behavior, controller aggregation, tray events, and settings
    reusable when another keyboard package is added.
    """

    def __init__(
        self,
        config: MapperConfig,
        registry: KeyboardRegistry | None = None,
        controller_factory: Callable[[], ControllerOutput] = VirtualXboxController,
    ) -> None:
        self.events: queue.SimpleQueue[ServiceEvent] = queue.SimpleQueue()
        # The UI owns a mutable config object. The worker owns this validated
        # clone, which can be read without serializing the entire configuration
        # for every Hall report.
        self._config = MapperConfig.from_dict(config.to_dict())
        self._config_revision = 0
        self._config_lock = threading.RLock()
        self._registry = registry or KeyboardRegistry()
        self._controller_factory = controller_factory
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected_devices: set[str] = set()
        self._sessions: dict[str, _KeyboardControllerSession] = {}
        self._session_lock = threading.RLock()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def connected(self) -> bool:
        with self._session_lock:
            return bool(self._connected_devices)

    @property
    def registry(self) -> KeyboardRegistry:
        return self._registry

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="Hall keyboard mapper", daemon=True)
        self._thread.start()
        self.events.put(ServiceEvent("started", "Auto-detecting Hall-effect keyboards..."))

    def stop(self, timeout: float = 4.0) -> None:
        self._stop.set()
        self._wake.set()
        self._stop_all_sessions(timeout=timeout)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)
        self.events.put(ServiceEvent("stopped", "Mapping stopped"))

    def update_config(self, config: MapperConfig) -> None:
        snapshot = MapperConfig.from_dict(config.to_dict())
        with self._config_lock:
            self._config = snapshot
            self._config_revision += 1
        self._wake.set()
        self.events.put(ServiceEvent("config", "Mapping updated"))

    def _config_snapshot(self) -> tuple[MapperConfig, int]:
        """Return the immutable-by-convention worker snapshot and revision."""

        with self._config_lock:
            return self._config, self._config_revision

    @staticmethod
    def _policy_key(config: MapperConfig, keyboard_id: str) -> tuple[bool, bool, frozenset[int]]:
        return (
            config.keyboard_keys_enabled,
            config.gamepad_mapping_override,
            frozenset(config.bound_key_ids(keyboard_id)),
        )

    def _apply_policy(self, adapter, config: MapperConfig, settings_id: str) -> tuple[bool, str]:
        policy = DigitalOutputPolicy(
            keyboard_keys_enabled=config.keyboard_keys_enabled,
            gamepad_mapping_override=config.gamepad_mapping_override,
        )
        return adapter.apply_digital_output_policy(policy, config.bound_key_ids(settings_id))

    def _run(self) -> None:
        last_revision = -1
        while not self._stop.is_set():
            config, revision = self._config_snapshot()
            if revision != last_revision:
                self._reconcile_sessions(config)
                last_revision = revision
            else:
                self._reconcile_sessions(config)
            self._wake.wait(2.0)
            self._wake.clear()
        self._stop_all_sessions()

    def _target_selection_ids(self, config: MapperConfig) -> tuple[str, ...]:
        devices = self._registry.enumerate_devices()
        if not devices and config.preferred_keyboard != "auto":
            # Compatibility fallback for simple third-party adapters/tests that
            # can connect by adapter id but do not yet implement pre-open device
            # enumeration. Built-in adapters enumerate physical devices, so the
            # normal path still creates one controller per plugged-in keyboard.
            settings = config.settings_for(config.preferred_keyboard)
            return (config.preferred_keyboard,) if settings.controller_enabled else ()
        if not devices:
            # Older adapters may support ``connect("auto")`` before they learn
            # to list each physical board. The session still creates its
            # virtual controller only after a keyboard connects successfully.
            return ("auto",)
        return tuple(
            device.selection_id
            for device in devices
            if config.settings_for(device.selection_id).controller_enabled
        )

    def _reconcile_sessions(self, config: MapperConfig) -> None:
        try:
            targets = set(self._target_selection_ids(config))
        except Exception as error:
            self.events.put(ServiceEvent("searching", f"Looking for supported keyboards... {error}"))
            targets = set()

        stale: list[_KeyboardControllerSession] = []
        with self._session_lock:
            for selection_id, session in list(self._sessions.items()):
                if selection_id not in targets or not session.alive:
                    stale.append(session)
                    self._sessions.pop(selection_id, None)
            for selection_id in sorted(targets):
                if selection_id in self._sessions:
                    continue
                session = _KeyboardControllerSession(selection_id, self)
                self._sessions[selection_id] = session
                session.start()

            active = len(self._connected_devices)
        for session in stale:
            session.stop(timeout=0.8)

        if not active:
            self.events.put(
                ServiceEvent(
                    "searching",
                    "Enable controller mode on a connected supported keyboard to create a virtual controller.",
                )
            )
        else:
            label = "keyboard" if active == 1 else "keyboards"
            self.events.put(ServiceEvent("running", f"Controller mode active for {active} {label}."))

    def _stop_all_sessions(self, timeout: float = 2.0) -> None:
        with self._session_lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._connected_devices.clear()
        for session in sessions:
            session.stop(timeout=timeout)

    def _session_connected(self, device_id: str) -> None:
        with self._session_lock:
            self._connected_devices.add(device_id)

    def _session_disconnected(self, device_id: str) -> None:
        with self._session_lock:
            self._connected_devices.discard(device_id)
