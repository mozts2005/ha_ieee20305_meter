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
        "name": "Active Power",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "instantaneous_demand_w": {
        "name": "Instantaneous Demand",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "voltage_v": {
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "current_a": {
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "energy_wh": {
        "name": "Energy",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "current_summation_delivered_wh": {
        "name": "Current Summation Delivered",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "current_summation_received_wh": {
        "name": "Current Summation Received",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "wh_interval_delivered_wh": {
        "name": "Wh Interval Delivered",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    "wh_interval_received_wh": {
        "name": "Wh Interval Received",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL,
    },
    "tou_wh_delivered_wh": {
        "name": "TOU Wh Delivered",
        "unit": UnitOfEnergy.WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "vah_delivered_vah": {
        "name": "VAh Delivered",
        "unit": "VAh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "varh_delivered_varh": {
        "name": "VARh Delivered",
        "unit": "varh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "max_demand_delivered_w": {
        "name": "Max Demand Delivered",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "power_factor_abc": {
        "name": "Power Factor ABC",
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
    async_add_entities(entities)


class IEEE20305Sensor(CoordinatorEntity[IEEE20305DataUpdateCoordinator], SensorEntity):
    """Sensor mapped to one telemetry key."""

    def __init__(
        self,
        coordinator: IEEE20305DataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        meta: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = meta["name"]
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


class IEEE20305LfdiSensor(CoordinatorEntity[IEEE20305DataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor exposing certificate LFDI."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: IEEE20305DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_name = "LFDI"
        self._attr_unique_id = f"{entry.entry_id}_lfdi"
        self._attr_device_info = _meter_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return certificate LFDI."""
        return self.coordinator.lfdi
