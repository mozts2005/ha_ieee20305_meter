from unittest.mock import AsyncMock

import pytest

from ieee20305_client.client import IEEE20305Client, IEEE20305ClientConfig


def _client() -> IEEE20305Client:
    return IEEE20305Client(
        IEEE20305ClientConfig(
            endpoint="https://meter.local:8081",
            client_cert="/tmp/client.crt",
            client_key="/tmp/client.key",
            ca_cert="/tmp/ca.crt",
        )
    )


def _client_with_version(agent_version: str) -> IEEE20305Client:
    return IEEE20305Client(
        IEEE20305ClientConfig(
            endpoint="https://meter.local:8081",
            client_cert="/tmp/client.crt",
            client_key="/tmp/client.key",
            ca_cert="/tmp/ca.crt",
            agent_version=agent_version,
        )
    )


@pytest.mark.asyncio
async def test_fetch_telemetry_discovers_meter_readings_from_xml() -> None:
    client = _client()
    client._fetch_direct_json = AsyncMock(side_effect=ValueError("not json"))

    responses = {
        "/dcap": """
            <DeviceCapability xmlns=\"urn:ieee:std:2030.5:ns\">
              <UsagePointListLink href=\"/upt\" />
            </DeviceCapability>
        """,
        "/upt": """
            <UsagePointList xmlns=\"urn:ieee:std:2030.5:ns\">
              <UsagePoint href=\"/upt/1\">
                <MeterReadingListLink href=\"/upt/1/mr\" all=\"3\" />
              </UsagePoint>
            </UsagePointList>
        """,
        "/upt/1/mr": """
            <MeterReadingList xmlns=\"urn:ieee:std:2030.5:ns\">
              <MeterReading href=\"/upt/1/mr/0\">
                <ReadingLink href=\"/upt/1/mr/0/r\" />
                <ReadingTypeLink href=\"/rt/0\" />
              </MeterReading>
              <MeterReading href=\"/upt/1/mr/1\">
                <ReadingLink href=\"/upt/1/mr/1/r\" />
                <ReadingTypeLink href=\"/rt/1\" />
              </MeterReading>
              <MeterReading href=\"/upt/1/mr/2\">
                <ReadingLink href=\"/upt/1/mr/2/r\" />
                <ReadingTypeLink href=\"/rt/2\" />
              </MeterReading>
            </MeterReadingList>
        """,
        "/rt/0": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><description>Instantaneous Demand</description></ReadingType>",
        "/rt/1": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><description>Current Summation Delivered</description></ReadingType>",
        "/rt/2": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><description>Current Summation Received</description></ReadingType>",
        "/upt/1/mr/0/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>321</value></Reading>",
        "/upt/1/mr/1/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>2000</value></Reading>",
        "/upt/1/mr/2/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>100</value></Reading>",
    }

    async def _request_text(path_or_url: str) -> str:
        return responses[path_or_url]

    client._request_text = AsyncMock(side_effect=_request_text)

    telemetry = await client.fetch_telemetry()

    assert telemetry.instantaneous_demand_w == 321.0
    assert telemetry.active_power_w == 321.0
    assert telemetry.voltage_v is None
    assert telemetry.current_a is None
    assert telemetry.current_summation_delivered_wh == 2000.0
    assert telemetry.current_summation_received_wh == 100.0
    assert telemetry.energy_wh == 2000.0


@pytest.mark.asyncio
async def test_fetch_telemetry_classifies_reading_types_from_numeric_attributes() -> None:
    client = _client()
    client._fetch_direct_json = AsyncMock(side_effect=ValueError("not json"))

    responses = {
        "/dcap": """
            <DeviceCapability xmlns=\"urn:ieee:std:2030.5:ns\">
              <UsagePointListLink href=\"/upt\" />
            </DeviceCapability>
        """,
        "/upt": """
            <UsagePointList xmlns=\"urn:ieee:std:2030.5:ns\">
              <UsagePoint href=\"/upt/1\">
                <MeterReadingListLink href=\"/upt/1/mr\" all=\"3\" />
              </UsagePoint>
            </UsagePointList>
        """,
        "/upt/1/mr": """
            <MeterReadingList xmlns=\"urn:ieee:std:2030.5:ns\">
              <MeterReading href=\"/upt/1/mr/0\">
                <ReadingLink href=\"/upt/1/mr/0/r\" />
                <ReadingTypeLink href=\"/rt/0\" />
              </MeterReading>
              <MeterReading href=\"/upt/1/mr/1\">
                <ReadingLink href=\"/upt/1/mr/1/r\" />
                <ReadingTypeLink href=\"/rt/1\" />
              </MeterReading>
              <MeterReading href=\"/upt/1/mr/2\">
                <ReadingLink href=\"/upt/1/mr/2/r\" />
                <ReadingTypeLink href=\"/rt/2\" />
              </MeterReading>
            </MeterReadingList>
        """,
        "/rt/0": """
            <ReadingType xmlns=\"urn:ieee:std:2030.5:ns\">
              <accumulationBehaviour>12</accumulationBehaviour>
              <flowDirection>1</flowDirection>
              <kind>8</kind>
              <uom>38</uom>
            </ReadingType>
        """,
        "/rt/1": """
            <ReadingType xmlns=\"urn:ieee:std:2030.5:ns\">
              <accumulationBehaviour>9</accumulationBehaviour>
              <flowDirection>1</flowDirection>
              <kind>12</kind>
              <uom>72</uom>
            </ReadingType>
        """,
        "/rt/2": """
            <ReadingType xmlns=\"urn:ieee:std:2030.5:ns\">
              <accumulationBehaviour>9</accumulationBehaviour>
              <flowDirection>19</flowDirection>
              <kind>12</kind>
              <uom>72</uom>
            </ReadingType>
        """,
        "/upt/1/mr/0/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>450</value></Reading>",
        "/upt/1/mr/1/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>1200</value></Reading>",
        "/upt/1/mr/2/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>80</value></Reading>",
    }

    async def _request_text(path_or_url: str) -> str:
        return responses[path_or_url]

    client._request_text = AsyncMock(side_effect=_request_text)

    telemetry = await client.fetch_telemetry()

    assert telemetry.active_power_w == 450.0
    assert telemetry.instantaneous_demand_w == 450.0
    assert telemetry.current_summation_delivered_wh == 1200.0
    assert telemetry.current_summation_received_wh == 80.0
    assert telemetry.energy_wh == 1200.0


def test_build_url_joins_relative_paths() -> None:
    client = _client()

    assert client._build_url("/dcap") == "https://meter.local:8081/dcap"
    assert client._build_url("https://example.test/foo") == "https://example.test/foo"


@pytest.mark.asyncio
async def test_fetch_telemetry_classifies_v3_additional_entities() -> None:
    client = _client_with_version("v3")
    client._fetch_direct_json = AsyncMock(side_effect=ValueError("not json"))

    responses = {
        "/dcap": "<DeviceCapability xmlns=\"urn:ieee:std:2030.5:ns\"><UsagePointListLink href=\"/upt\" /></DeviceCapability>",
        "/upt": "<UsagePointList xmlns=\"urn:ieee:std:2030.5:ns\"><UsagePoint href=\"/upt/1\"><MeterReadingListLink href=\"/upt/1/mr\" all=\"5\" /></UsagePoint></UsagePointList>",
        "/upt/1/mr": """
        <MeterReadingList xmlns=\"urn:ieee:std:2030.5:ns\">
          <MeterReading href=\"/upt/1/mr/10\"><ReadingSetListLink href=\"/upt/1/mr/10/rs\" /><ReadingTypeLink href=\"/rt/10\" /></MeterReading>
          <MeterReading href=\"/upt/1/mr/11\"><ReadingSetListLink href=\"/upt/1/mr/11/rs\" /><ReadingTypeLink href=\"/rt/11\" /></MeterReading>
          <MeterReading href=\"/upt/1/mr/12\"><ReadingLink href=\"/upt/1/mr/12/r\" /><ReadingTypeLink href=\"/rt/12\" /></MeterReading>
          <MeterReading href=\"/upt/1/mr/13\"><ReadingLink href=\"/upt/1/mr/13/r\" /><ReadingTypeLink href=\"/rt/13\" /></MeterReading>
          <MeterReading href=\"/upt/1/mr/14\"><ReadingLink href=\"/upt/1/mr/14/r\" /><ReadingTypeLink href=\"/rt/14\" /></MeterReading>
        </MeterReadingList>
      """,
        "/rt/10": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><accumulationBehaviour>4</accumulationBehaviour><flowDirection>1</flowDirection><kind>12</kind><uom>72</uom></ReadingType>",
        "/rt/11": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><accumulationBehaviour>9</accumulationBehaviour><flowDirection>1</flowDirection><kind>12</kind><uom>72</uom><numberOfTouTiers>3</numberOfTouTiers></ReadingType>",
        "/rt/12": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><accumulationBehaviour>9</accumulationBehaviour><flowDirection>1</flowDirection><kind>12</kind><uom>71</uom></ReadingType>",
        "/rt/13": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><accumulationBehaviour>12</accumulationBehaviour><dataQualifier>8</dataQualifier><flowDirection>1</flowDirection><kind>8</kind><uom>38</uom></ReadingType>",
        "/rt/14": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><phase>224</phase><uom>65</uom></ReadingType>",
        "/upt/1/mr/10/rs": "<ReadingSetList xmlns=\"urn:ieee:std:2030.5:ns\"><ReadingSet href=\"/upt/1/mr/10/rs/0\"><ReadingListLink href=\"/upt/1/mr/10/rs/0/r\" /></ReadingSet></ReadingSetList>",
        "/upt/1/mr/11/rs": "<ReadingSetList xmlns=\"urn:ieee:std:2030.5:ns\"><ReadingSet href=\"/upt/1/mr/11/rs/0\"><ReadingListLink href=\"/upt/1/mr/11/rs/0/r\" /></ReadingSet></ReadingSetList>",
        "/upt/1/mr/10/rs/0/r": "<ReadingList xmlns=\"urn:ieee:std:2030.5:ns\"><Reading><value>55</value></Reading></ReadingList>",
        "/upt/1/mr/11/rs/0/r": "<ReadingList xmlns=\"urn:ieee:std:2030.5:ns\"><Reading><value>77</value></Reading></ReadingList>",
        "/upt/1/mr/12/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>88</value></Reading>",
        "/upt/1/mr/13/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>99</value></Reading>",
        "/upt/1/mr/14/r": "<Reading xmlns=\"urn:ieee:std:2030.5:ns\"><value>0.96</value></Reading>",
    }

    async def _request_text(path_or_url: str) -> str:
        return responses[path_or_url]

    client._request_text = AsyncMock(side_effect=_request_text)

    telemetry = await client.fetch_telemetry()

    assert telemetry.active_power_w is None
    assert telemetry.wh_interval_delivered_wh == 55.0
    assert telemetry.tou_wh_delivered_wh == 77.0
    assert telemetry.vah_delivered_vah == 88.0
    assert telemetry.max_demand_delivered_w == 99.0
    assert telemetry.power_factor_abc == 0.96


@pytest.mark.asyncio
async def test_fetch_telemetry_omits_v3_entities_when_configured_for_v1() -> None:
    client = _client_with_version("v1")
    client._fetch_direct_json = AsyncMock(side_effect=ValueError("not json"))

    responses = {
        "/dcap": "<DeviceCapability xmlns=\"urn:ieee:std:2030.5:ns\"><UsagePointListLink href=\"/upt\" /></DeviceCapability>",
        "/upt": "<UsagePointList xmlns=\"urn:ieee:std:2030.5:ns\"><UsagePoint href=\"/upt/1\"><MeterReadingListLink href=\"/upt/1/mr\" all=\"1\" /></UsagePoint></UsagePointList>",
        "/upt/1/mr": "<MeterReadingList xmlns=\"urn:ieee:std:2030.5:ns\"><MeterReading href=\"/upt/1/mr/10\"><ReadingSetListLink href=\"/upt/1/mr/10/rs\" /><ReadingTypeLink href=\"/rt/10\" /></MeterReading></MeterReadingList>",
        "/rt/10": "<ReadingType xmlns=\"urn:ieee:std:2030.5:ns\"><accumulationBehaviour>4</accumulationBehaviour><flowDirection>1</flowDirection><kind>12</kind><uom>72</uom></ReadingType>",
        "/upt/1/mr/10/rs": "<ReadingSetList xmlns=\"urn:ieee:std:2030.5:ns\"><ReadingSet href=\"/upt/1/mr/10/rs/0\"><ReadingListLink href=\"/upt/1/mr/10/rs/0/r\" /></ReadingSet></ReadingSetList>",
        "/upt/1/mr/10/rs/0/r": "<ReadingList xmlns=\"urn:ieee:std:2030.5:ns\"><Reading><value>55</value></Reading></ReadingList>",
    }

    async def _request_text(path_or_url: str) -> str:
        return responses[path_or_url]

    client._request_text = AsyncMock(side_effect=_request_text)

    telemetry = await client.fetch_telemetry()

    assert telemetry.active_power_w is None
    assert telemetry.energy_wh is None
    assert telemetry.wh_interval_delivered_wh is None