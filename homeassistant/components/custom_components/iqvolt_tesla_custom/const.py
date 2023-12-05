"""Const file for Tesla cars."""
VERSION = "1.0.0"
CONF_EXPIRATION = "expiration"
CONF_INCLUDE_VEHICLES = "include_vehicles"
CONF_POLLING_POLICY = "polling_policy"
CONF_WAKE_ON_START = "enable_wake_on_start"
CONF_ENABLE_TESLAMATE = "enable_teslamate"
DOMAIN = "iqvolt_tesla_custom"
ATTRIBUTION = "Data provided by Tesla"
DATA_LISTENER = "listener"
DEFAULT_SCAN_INTERVAL = 660
DEFAULT_WAKE_ON_START = False
DEFAULT_ENABLE_TESLAMATE = False
ERROR_URL_NOT_DETECTED = "url_not_detected"
MIN_SCAN_INTERVAL = 10

PLATFORMS = [
    "sensor",
    "lock",
    "climate",
    "cover",
    "binary_sensor",
    "device_tracker",
    "switch",
    "button",
    "select",
    "update",
    "number",
    "text",
]

ATTR_PARAMETERS = "parameters"
ATTR_PATH_VARS = "path_vars"
ATTR_POLLING_POLICY_NORMAL = "normal"
ATTR_POLLING_POLICY_CONNECTED = "connected"
ATTR_POLLING_POLICY_ALWAYS = "always"
ATTR_VIN = "vin"
DEFAULT_POLLING_POLICY = ATTR_POLLING_POLICY_NORMAL
DISTANCE_UNITS_KM_HR = "km/hr"
SERVICE_API = "api"
SERVICE_SCAN_INTERVAL = "polling_interval"
