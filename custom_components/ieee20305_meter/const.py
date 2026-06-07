"""Constants for the IEEE 2030.5 meter integration."""

DOMAIN = "ieee20305_meter"
PLATFORMS = ["sensor"]

CONF_ENDPOINT = "endpoint"
CONF_METER_HOST = "meter_host"
CONF_METER_PORT = "meter_port"
CONF_CLIENT_CERT = "client_cert"
CONF_CLIENT_KEY = "client_key"
CONF_CA_CERT = "ca_cert"
CONF_POLL_INTERVAL = "poll_interval"
CONF_MODE = "mode"
CONF_SHOW_LFDI = "show_lfdi"
CONF_AGENT_VERSION = "agent_version"

DEFAULT_CLIENT_CERT_PATH = f"{DOMAIN}/certs/client.crt"
DEFAULT_CLIENT_KEY_PATH = f"{DOMAIN}/certs/client.key"
DEFAULT_CA_CERT_PATH = f"{DOMAIN}/certs/ca.crt"

DEFAULT_METER_PORT = 8081
DEFAULT_POLL_INTERVAL = 30
DEFAULT_MODE = "simulator"
DEFAULT_SHOW_LFDI = True
DEFAULT_AGENT_VERSION = "auto"
MODES = ["simulator", "real"]
AGENT_VERSIONS = ["auto", "v1", "v3"]

DATA_COORDINATOR = "coordinator"
