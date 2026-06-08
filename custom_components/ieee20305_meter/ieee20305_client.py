"""Embedded IEEE 2030.5 client for Home Assistant runtime.

This module is kept inside the custom integration so HACS installs are self-contained.
"""

from __future__ import annotations

from dataclasses import dataclass
import ssl
from xml.etree import ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp


@dataclass(frozen=True)
class IEEE20305ClientConfig:
    """Runtime config for connecting to IEEE 2030.5 endpoint."""

    endpoint: str
    client_cert: str
    client_key: str
    ca_cert: str
    mode: str = "simulator"
    agent_version: str = "auto"
    timeout_seconds: int = 15


@dataclass(frozen=True)
class TelemetrySample:
    """Normalized telemetry payload."""

    active_power_w: float | None
    voltage_v: float | None
    current_a: float | None
    energy_wh: float | None
    current_summation_delivered_wh: float | None = None
    current_summation_received_wh: float | None = None
    instantaneous_demand_w: float | None = None
    wh_interval_delivered_wh: float | None = None
    wh_interval_received_wh: float | None = None
    tou_wh_delivered_wh: float | None = None
    vah_delivered_vah: float | None = None
    varh_delivered_varh: float | None = None
    max_demand_delivered_w: float | None = None
    power_factor_abc: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "active_power_w": self.active_power_w,
            "voltage_v": self.voltage_v,
            "current_a": self.current_a,
            "energy_wh": self.energy_wh,
            "current_summation_delivered_wh": self.current_summation_delivered_wh,
            "current_summation_received_wh": self.current_summation_received_wh,
            "instantaneous_demand_w": self.instantaneous_demand_w,
            "wh_interval_delivered_wh": self.wh_interval_delivered_wh,
            "wh_interval_received_wh": self.wh_interval_received_wh,
            "tou_wh_delivered_wh": self.tou_wh_delivered_wh,
            "vah_delivered_vah": self.vah_delivered_vah,
            "varh_delivered_varh": self.varh_delivered_varh,
            "max_demand_delivered_w": self.max_demand_delivered_w,
            "power_factor_abc": self.power_factor_abc,
        }


class IEEE20305Client:
    """Fetch and normalize meter telemetry over HTTPS."""

    def __init__(self, config: IEEE20305ClientConfig) -> None:
        self._config = config

    async def fetch_telemetry(self) -> TelemetrySample:
        try:
            payload = await self._fetch_direct_json()
        except (aiohttp.ClientError, ValueError):
            payload = await self._fetch_via_discovery()
            if self._config.mode == "real" and not self._has_meaningful_telemetry(payload):
                payload = await self._fetch_via_xcel_fixed_paths()
        return self._normalize_payload(payload)

    def _has_meaningful_telemetry(self, payload: dict[str, float | None]) -> bool:
        return any(value is not None for value in payload.values())

    async def _fetch_direct_json(self) -> dict[str, Any]:
        data = await self._request_json(self._config.endpoint)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object payload")
        return data

    async def _request_json(self, path_or_url: str) -> Any:
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
        ssl_context = self._build_ssl_context()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self._build_url(path_or_url), ssl=ssl_context) as response:
                response.raise_for_status()
                data = await response.json()

        return data

    async def _request_text(self, path_or_url: str) -> str:
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
        ssl_context = self._build_ssl_context()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self._build_url(path_or_url), ssl=ssl_context) as response:
                response.raise_for_status()
                return await response.text()

    async def _fetch_via_discovery(self) -> dict[str, float | None]:
        device_capability_xml = await self._request_text("/dcap")
        usage_point_list_href = self._find_link_href(device_capability_xml, "UsagePointListLink")
        if usage_point_list_href is None:
            raise ValueError("Device capability did not include UsagePointListLink")

        usage_point_list_xml = await self._request_text(usage_point_list_href)
        meter_reading_list_href = self._find_first_descendant_link_href(
            usage_point_list_xml,
            parent_name="UsagePoint",
            link_name="MeterReadingListLink",
        )
        if meter_reading_list_href is None:
            raise ValueError("Usage point did not include MeterReadingListLink")

        meter_reading_list_xml = await self._request_text(meter_reading_list_href)
        telemetry: dict[str, float | None] = {
            "active_power_w": None,
            "voltage_v": None,
            "current_a": None,
            "energy_wh": None,
            "current_summation_delivered_wh": None,
            "current_summation_received_wh": None,
            "instantaneous_demand_w": None,
            "wh_interval_delivered_wh": None,
            "wh_interval_received_wh": None,
            "tou_wh_delivered_wh": None,
            "vah_delivered_vah": None,
            "varh_delivered_varh": None,
            "max_demand_delivered_w": None,
            "power_factor_abc": None,
        }

        root = ET.fromstring(meter_reading_list_xml)
        for meter_reading in self._find_children(root, "MeterReading"):
            reading_type_link = self._find_child(meter_reading, "ReadingTypeLink")
            if reading_type_link is None:
                continue

            reading_key = await self._resolve_reading_key(reading_type_link.attrib.get("href", ""))
            if reading_key is None:
                continue

            value = await self._read_meter_reading_value(meter_reading)
            if value is None:
                continue

            telemetry[reading_key] = value
            if reading_key == "instantaneous_demand_w":
                telemetry["active_power_w"] = value
            if reading_key == "current_summation_delivered_wh" and telemetry["energy_wh"] is None:
                telemetry["energy_wh"] = value

        return telemetry

    async def _fetch_via_xcel_fixed_paths(self) -> dict[str, float | None]:
        """Fallback for meters that expose values on fixed reading indexes."""
        telemetry: dict[str, float | None] = {
            "active_power_w": None,
            "voltage_v": None,
            "current_a": None,
            "energy_wh": None,
            "current_summation_delivered_wh": None,
            "current_summation_received_wh": None,
            "instantaneous_demand_w": None,
            "wh_interval_delivered_wh": None,
            "wh_interval_received_wh": None,
            "tou_wh_delivered_wh": None,
            "vah_delivered_vah": None,
            "varh_delivered_varh": None,
            "max_demand_delivered_w": None,
            "power_factor_abc": None,
        }

        for index in range(1, 23):
            try:
                reading_type_xml = await self._request_text(f"/rt/{index}")
                reading_key = self._classify_reading_type_xml(reading_type_xml)
                if reading_key is None:
                    continue

                meter_reading_xml = await self._request_text(f"/upt/1/mr/{index}")
                meter_reading = ET.fromstring(meter_reading_xml)
                value = await self._read_meter_reading_value(meter_reading)
                if value is None:
                    continue

                telemetry[reading_key] = value
                if reading_key == "instantaneous_demand_w":
                    telemetry["active_power_w"] = value
                if reading_key == "current_summation_delivered_wh" and telemetry["energy_wh"] is None:
                    telemetry["energy_wh"] = value
            except (aiohttp.ClientError, ET.ParseError, ValueError):
                continue

        return telemetry

    async def _resolve_reading_key(self, reading_type_href: str) -> str | None:
        reading_type_xml = await self._request_text(reading_type_href)
        reading_key = self._classify_reading_type_xml(reading_type_xml)
        if reading_key is not None:
            return reading_key

        description = self._find_text(reading_type_xml, "description")
        if description is None:
            return None

        normalized = description.strip().lower()
        if "instantaneous demand" in normalized:
            return "instantaneous_demand_w"
        if "current summation delivered" in normalized:
            return "current_summation_delivered_wh"
        if "current summation received" in normalized:
            return "current_summation_received_wh"
        if normalized == "energy":
            return "energy_wh"
        return None

    def _classify_reading_type_xml(self, reading_type_xml: str) -> str | None:
        accumulation = self._find_text(reading_type_xml, "accumulationBehaviour")
        data_qualifier = self._find_text(reading_type_xml, "dataQualifier")
        flow_direction = self._find_text(reading_type_xml, "flowDirection")
        kind = self._find_text(reading_type_xml, "kind")
        uom = self._find_text(reading_type_xml, "uom")
        phase = self._find_text(reading_type_xml, "phase")
        number_of_tou_tiers = self._find_text(reading_type_xml, "numberOfTouTiers")

        if self._matches_enum(accumulation, "12", "instantaneous") and self._matches_enum(
            kind, "8", "demand"
        ) and self._matches_enum(uom, "38", "watts") and not self._matches_enum(
            data_qualifier, "8", "maximum"
        ):
            return "instantaneous_demand_w"

        if self._matches_enum(accumulation, "4", "deltadata") and self._matches_enum(
            uom, "72", "wh"
        ):
            if self._matches_enum(flow_direction, "1", "forward"):
                return self._allow_for_version("wh_interval_delivered_wh", minimum_version="v3")
            if self._matches_enum(flow_direction, "19", "reverse"):
                return self._allow_for_version("wh_interval_received_wh", minimum_version="v3")

        if self._matches_enum(uom, "72", "wh") and self._matches_enum(
            flow_direction, "1", "forward"
        ):
            if self._matches_enum(accumulation, "9", "summation") or self._matches_enum(
                accumulation, "3", "cumulative"
            ):
                if self._is_positive_int(number_of_tou_tiers):
                    return self._allow_for_version("tou_wh_delivered_wh", minimum_version="v3")
                return "current_summation_delivered_wh"

        if self._matches_enum(uom, "72", "wh") and self._matches_enum(
            flow_direction, "19", "reverse"
        ):
            if self._matches_enum(accumulation, "9", "summation") or self._matches_enum(
                accumulation, "3", "cumulative"
            ):
                return "current_summation_received_wh"

        if self._matches_enum(uom, "71", "vah") and self._matches_enum(
            flow_direction, "1", "forward"
        ):
            if self._matches_enum(accumulation, "9", "summation") or self._matches_enum(
                accumulation, "3", "cumulative"
            ):
                return self._allow_for_version("vah_delivered_vah", minimum_version="v3")

        if self._matches_enum(uom, "73", "varh") and self._matches_enum(
            flow_direction, "1", "forward"
        ):
            if self._matches_enum(accumulation, "9", "summation") or self._matches_enum(
                accumulation, "3", "cumulative"
            ):
                return self._allow_for_version("varh_delivered_varh", minimum_version="v3")

        if self._matches_enum(kind, "8", "demand") and self._matches_enum(uom, "38", "watts"):
            if self._matches_enum(accumulation, "12", "instantaneous") and self._matches_enum(
                data_qualifier, "8", "maximum"
            ):
                return self._allow_for_version("max_demand_delivered_w", minimum_version="v3")

        if self._matches_enum(uom, "65", "costheta") and self._matches_enum(
            phase, "224", "abc"
        ):
            return self._allow_for_version("power_factor_abc", minimum_version="v3")

        return None

    async def _read_meter_reading_value(self, meter_reading: ET.Element) -> float | None:
        reading_link = self._find_child(meter_reading, "ReadingLink")
        if reading_link is not None:
            reading_xml = await self._request_text(reading_link.attrib.get("href", ""))
            value = self._find_numeric_text(reading_xml, "value")
            if value is not None:
                return value

        reading_set_list_link = self._find_child(meter_reading, "ReadingSetListLink")
        if reading_set_list_link is None:
            return None

        reading_set_list_xml = await self._request_text(reading_set_list_link.attrib.get("href", ""))
        reading_list_href = self._find_first_descendant_link_href(
            reading_set_list_xml,
            parent_name="ReadingSet",
            link_name="ReadingListLink",
        )
        if reading_list_href is None:
            return None

        reading_list_xml = await self._request_text(reading_list_href)
        return self._find_numeric_text(reading_list_xml, "value")

    def _build_url(self, path_or_url: str) -> str:
        parsed = urlparse(path_or_url)
        if parsed.scheme and parsed.netloc:
            return path_or_url
        return urljoin(f"{self._config.endpoint.rstrip('/')}/", path_or_url.lstrip("/"))

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build TLS context compatible with physical meter TLS behavior."""
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.load_cert_chain(self._config.client_cert, self._config.client_key)
        ssl_context.set_ciphers("ECDHE-ECDSA-AES128-CCM8:@SECLEVEL=0")
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ssl_context.options |= ssl.OP_LEGACY_SERVER_CONNECT

        # Local meter interoperability path: skip server-cert validation.
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _normalize_payload(self, payload: dict[str, Any]) -> TelemetrySample:
        def _as_float(key: str) -> float:
            value = payload.get(key)
            if value is None:
                raise ValueError(f"Missing telemetry key: {key}")
            return float(value)

        def _optional_float(key: str) -> float | None:
            value = payload.get(key)
            if value is None:
                return None
            return float(value)

        active_power_w = _optional_float("active_power_w")
        if active_power_w is None:
            active_power_w = _optional_float("instantaneous_demand_w")

        delivered_wh = _optional_float("current_summation_delivered_wh")
        received_wh = _optional_float("current_summation_received_wh")
        energy_wh = _optional_float("energy_wh")
        if energy_wh is None:
            energy_wh = delivered_wh

        return TelemetrySample(
            active_power_w=active_power_w,
            voltage_v=_optional_float("voltage_v"),
            current_a=_optional_float("current_a"),
            energy_wh=energy_wh,
            current_summation_delivered_wh=delivered_wh,
            current_summation_received_wh=received_wh,
            instantaneous_demand_w=_optional_float("instantaneous_demand_w"),
            wh_interval_delivered_wh=_optional_float("wh_interval_delivered_wh"),
            wh_interval_received_wh=_optional_float("wh_interval_received_wh"),
            tou_wh_delivered_wh=_optional_float("tou_wh_delivered_wh"),
            vah_delivered_vah=_optional_float("vah_delivered_vah"),
            varh_delivered_varh=_optional_float("varh_delivered_varh"),
            max_demand_delivered_w=_optional_float("max_demand_delivered_w"),
            power_factor_abc=_optional_float("power_factor_abc"),
        )

    def _find_link_href(self, xml_text: str, link_name: str) -> str | None:
        root = ET.fromstring(xml_text)
        for element in root.iter():
            if self._local_name(element.tag) == link_name:
                return element.attrib.get("href")
        return None

    def _find_first_descendant_link_href(
        self, xml_text: str, parent_name: str, link_name: str
    ) -> str | None:
        root = ET.fromstring(xml_text)
        for parent in root.iter():
            if self._local_name(parent.tag) != parent_name:
                continue
            child = self._find_child(parent, link_name)
            if child is not None:
                return child.attrib.get("href")
        return None

    def _find_numeric_text(self, xml_text: str, tag_name: str) -> float | None:
        root = ET.fromstring(xml_text)
        for element in root.iter():
            if self._local_name(element.tag) == tag_name and element.text is not None:
                return float(element.text)
        return None

    def _find_text(self, xml_text: str, tag_name: str) -> str | None:
        root = ET.fromstring(xml_text)
        for element in root.iter():
            if self._local_name(element.tag) == tag_name:
                return element.text
        return None

    def _find_children(self, parent: ET.Element, child_name: str) -> list[ET.Element]:
        return [child for child in list(parent) if self._local_name(child.tag) == child_name]

    def _find_child(self, parent: ET.Element, child_name: str) -> ET.Element | None:
        for child in list(parent):
            if self._local_name(child.tag) == child_name:
                return child
        return None

    def _local_name(self, tag: str) -> str:
        return tag.split("}", 1)[-1]

    def _matches_enum(self, value: str | None, numeric: str, named: str) -> bool:
        if value is None:
            return False
        normalized = value.strip().lower()
        return normalized == numeric or normalized == named.lower()

    def _allow_for_version(self, key: str, minimum_version: str) -> str | None:
        configured = self._config.agent_version
        if configured == "auto":
            return key
        order = {"v1": 1, "v3": 3}
        if configured not in order or minimum_version not in order:
            return key
        if order[configured] >= order[minimum_version]:
            return key
        return None

    def _is_positive_int(self, value: str | None) -> bool:
        if value is None:
            return False
        try:
            return int(value) > 0
        except ValueError:
            return False
