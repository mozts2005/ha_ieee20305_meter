from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


class FakeAbortFlow(Exception):
    """Raised when a config flow detects a duplicate unique ID."""


class FakeConfigFlow:
    """Minimal stand-in for Home Assistant's ConfigFlow base."""

    def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain

    def __init__(self) -> None:
        self._unique_id: str | None = None
        self._configured_unique_ids: set[str] = set()

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        if self._unique_id in self._configured_unique_ids:
            raise FakeAbortFlow("already_configured")

    def async_show_form(self, *, step_id: str, data_schema: Any) -> dict[str, Any]:
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}


class FakeDataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator."""

    def __class_getitem__(cls, item: object) -> type[FakeDataUpdateCoordinator]:
        return cls

    def __init__(
        self,
        hass: Any,
        logger: Any,
        name: str,
        update_interval: timedelta,
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data: dict[str, Any] | None = None


class FakeUpdateFailed(Exception):
    """Minimal stand-in for UpdateFailed."""


def _install_homeassistant_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    voluptuous = ModuleType("voluptuous")
    voluptuous.Required = lambda key, default=None: key
    voluptuous.Optional = lambda key, default=None: key
    voluptuous.Coerce = lambda func: func
    voluptuous.Range = lambda **kwargs: (lambda value: value)
    voluptuous.In = lambda values: (lambda value: value)
    voluptuous.All = lambda *validators: (lambda value: value)
    voluptuous.Schema = lambda schema: schema

    homeassistant = ModuleType("homeassistant")
    config_entries = ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = FakeConfigFlow
    config_entries.ConfigEntry = object

    data_entry_flow = ModuleType("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict[str, Any]

    const = ModuleType("homeassistant.const")
    const.Platform = SimpleNamespace(SENSOR="sensor")

    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object

    helpers = ModuleType("homeassistant.helpers")
    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.DataUpdateCoordinator = FakeDataUpdateCoordinator
    update_coordinator.UpdateFailed = FakeUpdateFailed

    certs = ModuleType("custom_components.ieee20305_meter.certs")

    async def async_ensure_certificates(_hass: Any, data: dict[str, Any]) -> dict[str, Any]:
        return data

    certs.async_ensure_certificates = async_ensure_certificates
    certs.compute_lfdi = lambda _path: "STUBBEDLFDI"

    ieee20305_client = ModuleType("custom_components.ieee20305_meter.ieee20305_client")

    class IEEE20305ClientConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class IEEE20305Client:
        def __init__(self, config: Any) -> None:
            self.config = config

        async def fetch_telemetry(self) -> Any:
            raise RuntimeError("fetch_telemetry should be patched in test")

    ieee20305_client.IEEE20305ClientConfig = IEEE20305ClientConfig
    ieee20305_client.IEEE20305Client = IEEE20305Client

    modules = {
        "voluptuous": voluptuous,
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.data_entry_flow": data_entry_flow,
        "homeassistant.const": const,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.update_coordinator": update_coordinator,
        "custom_components.ieee20305_meter.certs": certs,
        "custom_components.ieee20305_meter.ieee20305_client": ieee20305_client,
    }

    homeassistant.config_entries = config_entries
    homeassistant.data_entry_flow = data_entry_flow
    homeassistant.const = const
    homeassistant.core = core
    homeassistant.helpers = helpers
    helpers.update_coordinator = update_coordinator

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def _reload_module(module_name: str) -> Any:
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


@dataclass
class FakeEntry:
    entry_id: str
    data: dict[str, Any]


class FakeConfigEntriesManager:
    def __init__(self) -> None:
        self.updated_entries: list[tuple[FakeEntry, dict[str, Any]]] = []
        self.forwarded: list[tuple[str, list[Any]]] = []
        self.unloaded: list[tuple[str, list[Any]]] = []
        self.unload_result = True

    def async_update_entry(self, entry: FakeEntry, *, data: dict[str, Any]) -> None:
        entry.data = data
        self.updated_entries.append((entry, data))

    async def async_forward_entry_setups(self, entry: FakeEntry, platforms: list[Any]) -> None:
        self.forwarded.append((entry.entry_id, platforms))

    async def async_unload_platforms(self, entry: FakeEntry, platforms: list[Any]) -> bool:
        self.unloaded.append((entry.entry_id, platforms))
        return self.unload_result


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.config = SimpleNamespace(config_dir="/tmp/ha-config")
        self.config_entries = FakeConfigEntriesManager()

    async def async_add_executor_job(self, target: Any, *args: Any) -> Any:
        return target(*args)


@pytest.mark.asyncio
async def test_config_flow_creates_entry_from_simple_user_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_homeassistant_stubs(monkeypatch)

    config_flow = _reload_module("custom_components.ieee20305_meter.config_flow")
    flow = config_flow.IEEE20305ConfigFlow()

    result = await flow.async_step_user(
        {
            "meter_host": "meter.local",
            "meter_port": 8443,
            "poll_interval": 60,
            "mode": "real",
            "agent_version": "v3",
            "show_lfdi": False,
            "migrate_existing_addon_paths": False,
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "IEEE 2030.5 Meter"
    assert result["data"]["endpoint"] == "https://meter.local:8443"
    assert result["data"]["agent_version"] == "v3"
    assert result["data"]["show_lfdi"] is False


@pytest.mark.asyncio
async def test_config_flow_migration_step_reuses_existing_certificate_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_homeassistant_stubs(monkeypatch)

    config_flow = _reload_module("custom_components.ieee20305_meter.config_flow")
    flow = config_flow.IEEE20305ConfigFlow()

    initial = await flow.async_step_user(
        {
            "meter_host": "192.168.10.5",
            "meter_port": 8081,
            "poll_interval": 30,
            "mode": "simulator",
            "agent_version": "auto",
            "show_lfdi": True,
            "migrate_existing_addon_paths": True,
        }
    )
    migrated = await flow.async_step_migrate_from_addon(
        {
            "cert_dir": "legacy/certs",
            "cert_file": "device.pem",
            "key_file": "device.key",
            "ca_file": "ca.pem",
        }
    )

    assert initial["type"] == "form"
    assert initial["step_id"] == "migrate_from_addon"
    assert migrated["type"] == "create_entry"
    assert Path(migrated["data"]["client_cert"]).as_posix().endswith("legacy/certs/device.pem")
    assert Path(migrated["data"]["client_key"]).as_posix().endswith("legacy/certs/device.key")
    assert Path(migrated["data"]["ca_cert"]).as_posix().endswith("legacy/certs/ca.pem")


@pytest.mark.asyncio
async def test_config_flow_aborts_when_meter_is_already_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_homeassistant_stubs(monkeypatch)

    config_flow = _reload_module("custom_components.ieee20305_meter.config_flow")
    flow = config_flow.IEEE20305ConfigFlow()
    flow._configured_unique_ids.add("https://meter.local:8081")

    with pytest.raises(FakeAbortFlow):
        await flow.async_step_user(
            {
                "meter_host": "meter.local",
                "meter_port": 8081,
                "poll_interval": 30,
                "mode": "simulator",
                "agent_version": "auto",
                "show_lfdi": True,
                "migrate_existing_addon_paths": False,
            }
        )


@pytest.mark.asyncio
async def test_async_setup_entry_bootstraps_certs_registers_coordinator_and_forwards_platforms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_homeassistant_stubs(monkeypatch)

    integration = _reload_module("custom_components.ieee20305_meter")
    coordinator_module = _reload_module("custom_components.ieee20305_meter.coordinator")
    const = importlib.import_module("custom_components.ieee20305_meter.const")

    hass = FakeHass()
    entry = FakeEntry(
        entry_id="entry-1",
        data={
            "endpoint": "https://meter.local:8081",
            "client_cert": "client.crt",
            "client_key": "client.key",
            "ca_cert": "ca.crt",
            "mode": "simulator",
            "agent_version": "auto",
            "poll_interval": 30,
        },
    )

    async def fake_ensure_certificates(_hass: Any, data: dict[str, Any]) -> dict[str, Any]:
        updated = dict(data)
        updated["client_cert"] = "/tmp/generated/client.crt"
        updated["client_key"] = "/tmp/generated/client.key"
        updated["ca_cert"] = "/tmp/generated/ca.crt"
        return updated

    class FakeCoordinator:
        def __init__(self, hass: Any, entry: FakeEntry) -> None:
            self.hass = hass
            self.entry = entry
            self.refreshed = False

        async def async_config_entry_first_refresh(self) -> None:
            self.refreshed = True

    monkeypatch.setattr(integration, "async_ensure_certificates", fake_ensure_certificates)
    monkeypatch.setattr(coordinator_module, "IEEE20305DataUpdateCoordinator", FakeCoordinator)

    result = await integration.async_setup_entry(hass, entry)

    assert result is True
    assert entry.data["client_cert"] == "/tmp/generated/client.crt"
    assert hass.config_entries.forwarded == [("entry-1", ["sensor"])]
    stored = hass.data[const.DOMAIN][entry.entry_id][const.DATA_COORDINATOR]
    assert isinstance(stored, FakeCoordinator)
    assert stored.refreshed is True


@pytest.mark.asyncio
async def test_async_unload_entry_cleans_up_domain_data(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_homeassistant_stubs(monkeypatch)

    integration = _reload_module("custom_components.ieee20305_meter")
    const = importlib.import_module("custom_components.ieee20305_meter.const")

    hass = FakeHass()
    hass.data = {const.DOMAIN: {"entry-1": {const.DATA_COORDINATOR: object()}}}
    entry = FakeEntry(entry_id="entry-1", data={})

    result = await integration.async_unload_entry(hass, entry)

    assert result is True
    assert hass.config_entries.unloaded == [("entry-1", ["sensor"])]
    assert hass.data[const.DOMAIN] == {}


@pytest.mark.asyncio
async def test_coordinator_returns_telemetry_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_homeassistant_stubs(monkeypatch)

    coordinator_module = _reload_module("custom_components.ieee20305_meter.coordinator")
    entry = FakeEntry(
        entry_id="entry-1",
        data={
            "endpoint": "https://meter.local:8081",
            "client_cert": "client.crt",
            "client_key": "client.key",
            "ca_cert": "ca.crt",
            "mode": "simulator",
            "agent_version": "v1",
            "poll_interval": 45,
        },
    )

    class FakeTelemetry:
        def to_dict(self) -> dict[str, float | None]:
            return {"instantaneous_demand_w": 1234.0}

    class FakeClient:
        def __init__(self, config: Any) -> None:
            self.config = config

        async def fetch_telemetry(self) -> FakeTelemetry:
            return FakeTelemetry()

    monkeypatch.setattr(coordinator_module, "IEEE20305Client", FakeClient)
    monkeypatch.setattr(coordinator_module, "compute_lfdi", lambda _path: "ABCDEF")

    coordinator = coordinator_module.IEEE20305DataUpdateCoordinator(FakeHass(), entry)
    result = await coordinator._async_update_data()

    assert result == {"instantaneous_demand_w": 1234.0}
    assert coordinator.update_interval == timedelta(seconds=45)
    assert coordinator.lfdi == "ABCDEF"
    assert coordinator._client.config.agent_version == "v1"


@pytest.mark.asyncio
async def test_coordinator_wraps_client_failures_in_update_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_homeassistant_stubs(monkeypatch)

    coordinator_module = _reload_module("custom_components.ieee20305_meter.coordinator")
    entry = FakeEntry(
        entry_id="entry-1",
        data={
            "endpoint": "https://meter.local:8081",
            "client_cert": "client.crt",
            "client_key": "client.key",
            "ca_cert": "ca.crt",
            "mode": "simulator",
            "agent_version": "auto",
            "poll_interval": 30,
        },
    )

    class FailingClient:
        def __init__(self, config: Any) -> None:
            self.config = config

        async def fetch_telemetry(self) -> Any:
            raise RuntimeError("connection reset")

    monkeypatch.setattr(coordinator_module, "IEEE20305Client", FailingClient)
    monkeypatch.setattr(coordinator_module, "compute_lfdi", lambda _path: "ABCDEF")

    coordinator = coordinator_module.IEEE20305DataUpdateCoordinator(FakeHass(), entry)

    with pytest.raises(FakeUpdateFailed, match="Unable to fetch IEEE 2030.5 telemetry") as exc_info:
        await coordinator._async_update_data()

    assert "Configured LFDI=ABCDEF" in str(exc_info.value)
    assert "Energy Providers portal" in str(exc_info.value)