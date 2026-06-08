# Home Assistant IEEE 2030.5 Meter Integration

![IEEE 2030.5 Meter Icon](./icon.svg)

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
2. Enter your meter host and port in the primary setup form.
3. Enable reuse of existing add-on certificate filenames if you want to keep the older file layout.
4. If enabled, enter the previous certificate directory and filenames.
5. Finish setup and verify the LFDI diagnostic sensor value.
6. Disable the old MQTT add-on after this integration is reporting data.

### Sensor Mapping For Energy Dashboard

| Legacy MQTT-oriented sensor | New integration sensor |
| --- | --- |
| `current_summation_delivered_value` | `Current Summation Delivered` |
| `current_summation_received_value` | `Current Summation Received` |
| `instantaneous_demand` | `Instantaneous Demand` |

## Configuration fields

- Meter host or IP address
- Meter port
- Poll interval (seconds)
- Mode (`simulator` or `real`)
- Meter agent version (`auto`, `v1`, or `v3`)
- Create LFDI diagnostic sensor (enabled by default)
- Optional reuse of existing add-on certificate filenames

On first integration startup, the integration checks the configured certificate paths and
automatically generates missing certificate/key material.

When enabled, the integration exposes a diagnostic sensor that displays the generated
client certificate LFDI.

The integration now uses IEEE 2030.5 discovery from `/dcap` and usage point resources by
default, instead of assuming a fixed telemetry endpoint path.

When agent version is set to `v3` or left on `auto`, the integration can classify and expose
additional entities such as interval Wh, TOU Wh, apparent/reactive energy, max demand, and
power factor when those readings are present on the meter.

## Physical local hardware testing

Use a single script that handles both cert bootstrap and direct mTLS probing:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_local_hardware_test.py --host 10.0.2.71
```

Default local hardware test behavior:

- Boots xcel-compatible certs when missing
- Probes only port `8081`
- Probes only path `/dcap`
- Uses cipher `ECDHE-ECDSA-AES128-CCM8`
- Enables legacy renegotiation compatibility
- Uses metadata from `.secrets/ieee20305/xcel-compat/metadata.json`

Generated local files are written under `.secrets/ieee20305/xcel-compat/`:

- `.cert.pem`
- `.key.pem`
- `metadata.json`

Security notes:

- `.secrets/` is gitignored so private keys are not committed.
- Keep private keys local and rotate if they are ever exposed.
- Use the generated absolute paths from `metadata.json` in integration configuration.

## Development notes

- The implementation uses `DataUpdateCoordinator` polling.
- No MQTT dependencies are used in code, manifest, or tests.
