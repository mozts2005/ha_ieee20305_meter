# Home Assistant IEEE 2030.5 Meter Integration

A Home Assistant custom integration for read-only IEEE 2030.5 energy meter telemetry.

## Scope (v1)

- Read-only telemetry sensors
- Polling over HTTPS (IEEE 2030.5 resources)
- Mutual TLS support (client cert, key, CA bundle)
- HACS custom integration install support

## Explicit non-scope

- MQTT transport or MQTT broker integration
- Write/control commands
- Event push subscriptions

## Repository layout

- `custom_components/ieee20305_meter`: Home Assistant integration
- `src/ieee20305_client`: reusable IEEE 2030.5 client library
- `tests`: unit and integration-oriented tests

## HACS install

1. Open HACS in Home Assistant.
2. Add this repository as a custom integration source.
3. Install `IEEE 2030.5 Meter`.
4. Restart Home Assistant.
5. Add integration from Settings > Devices & Services.

## Migrating From hassio-xcel-itron-mqtt

1. Install this integration via HACS and start setup.
2. Select `Migrate from Xcel Itron MQTT add-on` in the setup menu.
3. Enter your previous add-on values:
	- `meter_ip` and `meter_port`
	- certificate directory and filenames
4. Finish setup and verify the LFDI diagnostic sensor value.
5. Disable the old MQTT add-on after this integration is reporting data.

### Sensor Mapping For Energy Dashboard

| Legacy MQTT-oriented sensor | New integration sensor |
| --- | --- |
| `current_summation_delivered_value` | `Current Summation Delivered` |
| `current_summation_received_value` | `Current Summation Received` |
| `instantaneous_demand` | `Instantaneous Demand` |

## Configuration fields

- Endpoint URL
- Client certificate path (auto-generated if missing)
- Client key path (auto-generated if missing)
- CA certificate path (auto-generated if missing)
- Poll interval (seconds)
- Mode (`simulator` or `real`)
- Create LFDI diagnostic sensor (enabled by default)

On first integration startup, the integration checks the configured certificate paths and
automatically generates missing certificate/key material.

When enabled, the integration exposes a diagnostic sensor that displays the generated
client certificate LFDI.

## Development notes

- The implementation uses `DataUpdateCoordinator` polling.
- No MQTT dependencies are used in code, manifest, or tests.
