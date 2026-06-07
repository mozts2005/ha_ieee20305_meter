from ieee20305_client.client import IEEE20305Client, IEEE20305ClientConfig


def _client() -> IEEE20305Client:
    cfg = IEEE20305ClientConfig(
        endpoint="https://example.local:8081",
        client_cert="/tmp/client.crt",
        client_key="/tmp/client.key",
        ca_cert="/tmp/ca.crt",
    )
    return IEEE20305Client(cfg)


def test_normalize_payload_success() -> None:
    client = _client()
    sample = client._normalize_payload(
        {
            "active_power_w": 123.4,
            "voltage_v": 240.0,
            "current_a": 5.1,
            "energy_wh": 1000,
        }
    )

    assert sample.active_power_w == 123.4
    assert sample.voltage_v == 240.0
    assert sample.current_a == 5.1
    assert sample.energy_wh == 1000.0


def test_normalize_payload_migration_fields_supported() -> None:
    client = _client()
    sample = client._normalize_payload(
        {
            "instantaneous_demand_w": 321.0,
            "voltage_v": 240.0,
            "current_a": 1.5,
            "current_summation_delivered_wh": 2000,
            "current_summation_received_wh": 100,
        }
    )

    assert sample.active_power_w == 321.0
    assert sample.energy_wh == 2000.0
    assert sample.current_summation_delivered_wh == 2000.0
    assert sample.current_summation_received_wh == 100.0
    assert sample.instantaneous_demand_w == 321.0


def test_normalize_payload_allows_sparse_payload_without_energy() -> None:
    client = _client()
    sample = client._normalize_payload(
        {
            "active_power_w": 100,
            "voltage_v": 230,
            "current_a": 4,
        }
    )

    assert sample.active_power_w == 100.0
    assert sample.energy_wh is None
