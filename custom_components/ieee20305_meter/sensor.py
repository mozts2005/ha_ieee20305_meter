"""Sensor entities for IEEE 2030.5 telemetry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_METER_HOST,
    CONF_METER_PORT,
    CONF_SHOW_LFDI,
    DATA_COORDINATOR,
    DEFAULT_SHOW_LFDI,
    DOMAIN,
)
from .coordinator import IEEE20305DataUpdateCoordinator

SENSOR_DEFINITIONS: dict[str, dict[str, Any]] = {
    "active_power_w": {
        "translation_key": "active_power_w",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "instantaneous_demand_w": {
        "translation_key": "instantaneous_demand_w",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "voltage_v": {
        "translation_key": "voltage_v",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "current_a": {
        "translation_key": "current_a",
        "unit": UnitOfElectricCurrent.AMPERE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "energy_wh": {
        "translation_key": "energy_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "current_summation_delivered_wh": {
        "translation_key": "current_summation_delivered_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "current_summation_received_wh": {
        "translation_key": "current_summation_received_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "wh_interval_delivered_wh": {
        "translation_key": "wh_interval_delivered_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    "wh_interval_received_wh": {
        "translation_key": "wh_interval_received_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    "tou_wh_delivered_wh": {
        "translation_key": "tou_wh_delivered_wh",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "vah_delivered_vah": {
        "translation_key": "vah_delivered_vah",
        "unit": "VAh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "varh_delivered_varh": {
        "translation_key": "varh_delivered_varh",
        "unit": "varh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "max_demand_delivered_w": {
        "translation_key": "max_demand_delivered_w",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "power_factor_abc": {
        "translation_key": "power_factor_abc",
        "unit": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


def _meter_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build meter device metadata so entities group under one device."""
    meter_host = str(entry.options.get(CONF_METER_HOST, entry.data.get(CONF_METER_HOST, "meter")))
    meter_port = entry.options.get(CONF_METER_PORT, entry.data.get(CONF_METER_PORT))
    meter_name = getattr(entry, "title", None) or f"IEEE 2030.5 Meter ({meter_host})"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=meter_name,
        manufacturer="IEEE 2030.5",
        model="Smart Meter",
        configuration_url=f"https://{meter_host}:{meter_port}" if meter_port else f"https://{meter_host}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a config entry."""
    coordinator: IEEE20305DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [
        IEEE20305Sensor(coordinator=coordinator, entry=entry, key=key, meta=meta)
        for key, meta in SENSOR_DEFINITIONS.items()
    ]
    show_lfdi = entry.options.get(CONF_SHOW_LFDI, entry.data.get(CONF_SHOW_LFDI, DEFAULT_SHOW_LFDI))
    if show_lfdi:
        entities.append(IEEE20305LfdiSensor(coordinator=coordinator, entry=entry))

    # Always add connection status sensor for diagnostics
    entities.append(IEEE20305ConnectionStatusSensor(coordinator=coordinator, entry=entry))

    async_add_entities(entities)


class IEEE20305Sensor(CoordinatorEntity[IEEE20305DataUpdateCoordinator], SensorEntity):
    """Sensor mapped to one telemetry key."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IEEE20305DataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        meta: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = meta["translation_key"]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = _meter_device_info(entry)
        self._attr_native_unit_of_measurement = meta["unit"]
        self._attr_device_class = meta.get("device_class")
        self._attr_state_class = meta.get("state_class")

    @property
    def native_value(self) -> float | None:
        """Return latest value for this sensor."""
        data = self.coordinator.data or {}
        value = data.get(self._key)
        return float(value) if value is not None else None


class IEEE20305LfdiSensor(SensorEntity):
    """Diagnostic sensor exposing certificate LFDI.

    This sensor is independent of coordinator state to ensure LFDI
    is always available for meter registration, even if the meter
    connection fails.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "lfdi"

    def __init__(self, coordinator: IEEE20305DataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_lfdi"
        self._attr_device_info = _meter_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return certificate LFDI from coordinator.

        LFDI is computed during coordinator initialization from the device's
        certificate and is always available regardless of meter connectivity.
        """
        return self._coordinator.lfdi

    async def async_added_to_hass(self) -> None:
        """Register update listener when added to hass."""
        # Listen for any coordinator updates to refresh entity
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """LFDI is always available since it comes from the certificate."""
        return True


class IEEE20305ConnectionStatusSensor(SensorEntity):
    """Diagnostic sensor for connection status and error state.

    Displays whether the meter is connected, in backoff, or in error state.
    Helps administrators identify and troubleshoot connectivity issues.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:connection"
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"

    def __init__(self, coordinator: IEEE20305DataUpdateCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connection_status"
        self._attr_device_info = _meter_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return connection status string.

        Returns:
            - "connected": Meter is connected and responding normally
            - "error": Meter is in error state (max backoff reached)
            - "unknown": Initial state or connection status unknown
        """
        if self._coordinator.in_error_state:
            return "error"
        elif self._coordinator.last_update_success:
            return "connected"
        else:
            return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional diagnostic attributes."""
        return {
            "failed_attempts": self._coordinator._failed_attempts,
            "max_backoff_seconds": 900,
            "in_error_state": self._coordinator.in_error_state,
            "last_update_success": self._coordinator.last_update_success,
            "update_interval_seconds": int(self._coordinator.update_interval.total_seconds()),
        }

    @property
    def available(self) -> bool:
        """Status sensor is always available."""
        return True
