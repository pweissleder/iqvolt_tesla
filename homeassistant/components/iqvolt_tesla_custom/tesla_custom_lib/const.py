#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Tesla API.

For more details about this api, please refer to the documentation at
https://github.com/zabuldon/teslajsonpy
"""
IDLE_INTERVAL = 600  # interval after parking to check at regular update_interval
ONLINE_INTERVAL = 60  # interval for checking online state; does not hit individual cars
SLEEP_INTERVAL = 660  # interval required to let vehicle sleep; based on testing
DRIVING_INTERVAL = 60  # interval when driving detected
UPDATE_INTERVAL = 300  # Default polling interval for vehicle
WEBSOCKET_TIMEOUT = 11  # time for websocket to timeout
WAKE_TIMEOUT = 60  # max time to wait for vehicle to wake
WAKE_CHECK_INTERVAL = 2  # wait period between wake checks after a wake request
MAX_API_RETRY_TIME = 15  # how long to retry api calls
WRAPPER_API_KEY = "11112d24-db81-3548-b761-835a473ccb24"
BASE_URL = "https://5.75.190.138:34567/"


CONF_WRAPPER_API_KEY = "wrapper_api_key"
CONF_BASE_URL = "base_url"


TESLA_PRODUCT_TYPE_VEHICLES = "vehicles"

BACKUP_RESERVE_MAX = 100
BACKUP_RESERVE_MIN = 0
CHARGE_CURRENT_MIN = 0

