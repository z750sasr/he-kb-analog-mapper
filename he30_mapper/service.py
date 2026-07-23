"""Brand-independent background keyboard-to-controller service."""

from __future__ import annotations

import queue
import threading
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


class MapperService:
    """Own auto-detection, one keyboard adapter, and one virtual controller.

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
        self._config = config
        self._config_lock = threading.RLock()
        self._registry = registry or KeyboardRegistry()
        self._controller_factory = controller_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def connected(self) -> bool:
        return self._connected

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
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)
        self._connected = False
        self.events.put(ServiceEvent("stopped", "Mapping stopped"))

    def update_config(self, config: MapperConfig) -> None:
        with self._config_lock:
            self._config = config
        self.events.put(ServiceEvent("config", "Mapping updated"))

    def _current_config(self) -> MapperConfig:
        with self._config_lock:
            # A validated deep copy prevents UI mutations halfway through an
            # input report.
            return MapperConfig.from_dict(self._config.to_dict())

    @staticmethod
    def _policy_key(config: MapperConfig, keyboard_id: str) -> tuple[bool, bool, frozenset[int]]:
        return (
            config.keyboard_keys_enabled,
            config.gamepad_mapping_override,
            frozenset(config.bound_key_ids(keyboard_id)),
        )

    def _apply_policy(self, adapter, config: MapperConfig) -> tuple[bool, str]:
        policy = DigitalOutputPolicy(
            keyboard_keys_enabled=config.keyboard_keys_enabled,
            gamepad_mapping_override=config.gamepad_mapping_override,
        )
        return adapter.apply_digital_output_policy(policy, config.bound_key_ids(adapter.adapter_id))

    def _run(self) -> None:
        controller: ControllerOutput | None = None
        engine = MappingEngine(self._current_config())

        while not self._stop.is_set():
            adapter = None
            try:
                config = self._current_config()
                self.events.put(ServiceEvent("searching", "Auto-detecting a supported Hall-effect keyboard..."))
                adapter, identity = self._registry.connect(config.preferred_keyboard)
                engine.update_keyboard(identity.adapter_id)
                self.events.put(
                    ServiceEvent(
                        "detected",
                        f"Detected {identity.model_name}",
                        keyboard_id=identity.adapter_id,
                        keyboard_name=identity.model_name,
                        layout_id=identity.layout_id,
                        digital_output_supported=adapter.capabilities.digital_output_policy,
                    )
                )

                self.events.put(ServiceEvent("preparing", f"Preparing {identity.model_name} Hall telemetry..."))
                adapter.prepare()

                # Detection intentionally precedes controller creation so the UI
                # can still show the right keyboard and an actionable driver
                # error when ViGEmBus is missing.
                if controller is None:
                    controller = self._controller_factory()

                policy_key = self._policy_key(config, identity.adapter_id)
                policy_supported, policy_message = self._apply_policy(adapter, config)
                self.events.put(
                    ServiceEvent(
                        "policy",
                        policy_message,
                        keyboard_id=identity.adapter_id,
                        digital_output_supported=policy_supported,
                    )
                )

                self._connected = True
                self.events.put(
                    ServiceEvent(
                        "connected",
                        f"{identity.model_name} connected",
                        keyboard_id=identity.adapter_id,
                        keyboard_name=identity.model_name,
                        layout_id=identity.layout_id,
                        digital_output_supported=adapter.capabilities.digital_output_policy,
                    )
                )

                while not self._stop.is_set():
                    event = adapter.read_event(100)
                    config = self._current_config()

                    next_policy_key = self._policy_key(config, identity.adapter_id)
                    if next_policy_key != policy_key:
                        policy_key = next_policy_key
                        supported, message = self._apply_policy(adapter, config)
                        self.events.put(
                            ServiceEvent(
                                "policy",
                                message,
                                keyboard_id=identity.adapter_id,
                                digital_output_supported=supported,
                            )
                        )

                    if isinstance(event, LayerChangeEvent):
                        self.events.put(
                            ServiceEvent(
                                "profile",
                                f"Profile {event.profile_index + 1}, layer {event.display_layer}",
                                keyboard_id=identity.adapter_id,
                            )
                        )
                        continue
                    if not isinstance(event, KeyTravelEvent):
                        continue

                    calibration = TravelCalibration(config.deadzone_raw, config.max_raw)
                    normalized = adapter.normalize_travel(event.raw_value, calibration)
                    engine.update_config(config)
                    value, state = engine.update_value(event.key_id, normalized)
                    controller.apply(state)
                    self.events.put(
                        ServiceEvent(
                            "travel",
                            physical_index=event.key_id,
                            value=value,
                            raw_value=event.raw_value,
                            keyboard_id=identity.adapter_id,
                        )
                    )
            except Exception as error:
                kind = "error" if controller is None and adapter is not None else "disconnected"
                retry = "" if kind == "error" else " Retrying in 2 seconds..."
                self.events.put(ServiceEvent(kind, f"{error}{retry}"))
                if kind == "error":
                    break
            finally:
                self._connected = False
                if controller is not None:
                    try:
                        controller.apply(engine.clear())
                    except Exception:
                        pass
                if adapter is not None:
                    try:
                        adapter.close()
                    except Exception:
                        pass

            if not self._stop.wait(2.0):
                continue

        if controller is not None:
            try:
                controller.reset()
            except Exception:
                pass
            try:
                controller.close()
            except Exception:
                pass
