#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Tesla API.

For more details about this api, please refer to the documentation at
https://github.com/zabuldon/teslajsonpy
"""
import logging
from typing import Optional, Tuple

from .exceptions import TeslaException

_LOGGER = logging.getLogger(__name__)

DAY_SELECTION_MAP = {
    "all_week": False,
    "weekdays": True,
}


class TeslaCar:
    #  pylint: disable=too-many-public-methods
    """Represents a Tesla car.

    This class shouldn't be instantiated directly; it will be instantiated
    by :meth:`teslajsonpy.controller.generate_car_objects`.
    """

    def __init__(self, car: dict, controller, vehicle_data: dict) -> None:
        """Initialize TeslaCar."""
        self._car = car
        self._controller = controller
        self._vehicle_data = vehicle_data

    ## Properties

    # ------------------ General ------------------
    @property
    def display_name(self) -> str:
        """Return display name."""
        return self._car.get("display_name")

    @property
    def id(self) -> int:
        # pylint: disable=invalid-name
        """Return id."""
        return self._car.get("id")

    @property
    def state(self) -> str:
        """Return car state."""
        return self._car.get("state")

    @property
    def vehicle_id(self) -> int:
        """Return car id."""
        return self._car.get("vehicle_id")

    @property
    def vin(self) -> str:
        """Return car vin."""
        return self._car.get("vin")

    @property
    def data_available(self) -> bool:
        """Return if data from VEHICLE_DATA endpoint is available."""
        # self._vehicle_data gets updated with some data from VEHICLE_LIST endpoint
        # Only return True if data specifically from VEHICLE_DATA endpoint is available
        # vehicle_state is only from the VEHICLE_DATA endpoint
        if self._vehicle_data.get("vehicle_state", {}):
            return True
        return None

    @property
    def car_type(self) -> str:
        """Return car type."""
        return f"Model {str(self.vin[3]).upper()}"

    @property
    def car_version(self) -> str:
        """Return installed car software version."""
        return self._vehicle_data.get("vehicle_state", {}).get("car_version")

    # ------------------ Status ------------------

    @property
    def is_on(self) -> bool:
        """Return car is on."""
        return self._controller.is_car_online(vin=self.vin)

    @property
    def power(self) -> int:
        """Return power."""
        return self._vehicle_data.get("drive_state", {}).get("power")

    # ---------------- Battery ------------------

    @property
    def battery_level(self) -> float:
        """Return car battery level (SOC). This is not affected by temperature."""
        return self._vehicle_data.get("charge_state", {}).get("battery_level")

    @property
    def usable_battery_level(self) -> float:
        """Return car usable battery level (uSOE). This is the value used in the app and car."""
        return self._vehicle_data.get("charge_state", {}).get("usable_battery_level")

    @property
    def battery_range(self) -> float:
        """Return car battery range."""
        return self._vehicle_data.get("charge_state", {}).get("battery_range")

    # ---------------- Charging ------------------
    @property
    def charger_actual_current(self) -> int:
        """Return charger actual current."""
        return self._vehicle_data.get("charge_state", {}).get("charger_actual_current")

    @property
    def charge_current_request(self) -> int:
        """Return charge current request."""
        return self._vehicle_data.get("charge_state", {}).get("charge_current_request")

    @property
    def charge_current_request_max(self) -> int:
        """Return charge current request max."""
        return self._vehicle_data.get("charge_state", {}).get(
            "charge_current_request_max"
        )

    @property
    def charge_port_latch(self) -> str:
        """Return charger port latch state.

        Returns
            str: Engaged

        Other states?

        """
        return self._vehicle_data.get("charge_state", {}).get("charge_port_latch")

    @property
    def charge_energy_added(self) -> float:
        """Return charge energy added."""
        return self._vehicle_data.get("charge_state", {}).get("charge_energy_added")

    @property
    def charge_limit_soc(self) -> int:
        """Return charge limit soc."""
        return self._vehicle_data.get("charge_state", {}).get("charge_limit_soc")

    @property
    def charge_limit_soc_max(self) -> int:
        """Return charge limit soc max."""
        return self._vehicle_data.get("charge_state", {}).get("charge_limit_soc_max")

    @property
    def charge_limit_soc_min(self) -> int:
        """Return charge limit soc min."""
        return self._vehicle_data.get("charge_state", {}).get("charge_limit_soc_min")

    @property
    def charge_miles_added_rated(self) -> float:
        """Return charge rated miles added."""
        return self._vehicle_data.get("charge_state", {}).get(
            "charge_miles_added_rated"
        )

    @property
    def charger_phases(self) -> int:
        """Return charger phase."""
        return self._vehicle_data.get("charge_state", {}).get("charger_phases")

    @property
    def charger_power(self) -> int:
        """Return charger power."""
        return self._vehicle_data.get("charge_state", {}).get("charger_power")

    @property
    def charge_rate(self) -> str:
        """Return charge rate."""
        return self._vehicle_data.get("charge_state", {}).get("charge_rate")

    @property
    def charging_state(self) -> str:
        """Return charging state.

        Returns
            str: Charging, Stopped, Complete, Disconnected, NoPower
            None: When car is asleep

        """
        return self._vehicle_data.get("charge_state", {}).get("charging_state")

    @property
    def charger_voltage(self) -> int:
        """Return charger voltage."""
        return self._vehicle_data.get("charge_state", {}).get("charger_voltage")

    @property
    def conn_charge_cable(self) -> str:
        """Return charge cable connection."""
        return self._vehicle_data.get("charge_state", {}).get("conn_charge_cable")

    @property
    def fast_charger_present(self) -> bool:
        """Return fast charger present."""
        return self._vehicle_data.get("charge_state", {}).get("fast_charger_present")

    @property
    def fast_charger_brand(self) -> str:
        """Return fast charger brand."""
        return self._vehicle_data.get("charge_state", {}).get("fast_charger_brand")

    @property
    def fast_charger_type(self) -> str:
        """Return fast charger type."""
        return self._vehicle_data.get("charge_state", {}).get("fast_charger_type")

    @property
    def is_charge_port_door_open(self) -> bool:
        """Return charger port door open."""
        return self._vehicle_data.get("charge_state", {}).get("charge_port_door_open")

    @property
    def time_to_full_charge(self) -> float:
        """Return time to full charge."""
        return self._vehicle_data.get("charge_state", {}).get("time_to_full_charge")

    @property
    def scheduled_charging_mode(self) -> str:
        """Return 'Off', 'DepartBy', or 'StartAt' for schedule disabled, scheduled departure, and scheduled charging respectively."""
        return self._vehicle_data.get("charge_state", {}).get("scheduled_charging_mode")

    @property
    def is_scheduled_charging_pending(self) -> bool:
        """Return if scheduled charging is pending."""
        return self._vehicle_data.get("charge_state", {}).get(
            "scheduled_charging_pending"
        )

    @property
    def scheduled_charging_start_time_app(self) -> int:
        """Return the scheduled charging start time."""
        return self._vehicle_data.get("charge_state", {}).get(
            "scheduled_charging_start_time_app"
        )

    # ---------------- Location ------------------
    @property
    def heading(self) -> int:
        """Return heading."""
        return self._vehicle_data.get("drive_state", {}).get("heading")

    @property
    def longitude(self) -> float:
        """Return longitude."""
        return self._vehicle_data.get("drive_state", {}).get("longitude")

    @property
    def latitude(self) -> float:
        """Return latitude."""
        return self._vehicle_data.get("drive_state", {}).get("latitude")

    def native_heading(self) -> int:
        """Return native heading."""
        return self._vehicle_data.get("drive_state", {}).get("native_heading")

    @property
    def native_longitude(self) -> float:
        """Return native longitude."""
        return self._vehicle_data.get("drive_state", {}).get("native_longitude")

    @property
    def native_latitude(self) -> float:
        """Return native latitude."""
        return self._vehicle_data.get("drive_state", {}).get("native_latitude")

    @property
    def native_type(self) -> float:
        """Return native type."""
        return self._vehicle_data.get("drive_state", {}).get("native_type")

    @property
    def native_location_supported(self) -> int:
        """Return native location supported."""
        return self._vehicle_data.get("drive_state", {}).get(
            "native_location_supported"
        )

    # ------------------ Planned Charging ------------------
    @property
    def is_off_peak_charging_weekday_only(self) -> bool:
        """Return if off off peak charging is weekday only for scheduled departure."""
        return DAY_SELECTION_MAP.get(
            self._vehicle_data.get("charge_state", {}).get("off_peak_charging_times")
        )

    @property
    def off_peak_hours_end_time(self) -> int:
        """Return end of off peak hours in minutes after midnight for scheduled departure."""
        return self._vehicle_data.get("charge_state", {}).get("off_peak_hours_end_time")

    @property
    def is_preconditioning_enabled(self) -> bool:
        """Return if preconditioning is enabled for scheduled departure."""
        return self._vehicle_data.get("charge_state", {}).get("preconditioning_enabled")

    @property
    def is_preconditioning_weekday_only(self) -> bool:
        """Return if preconditioning is weekday only for scheduled departure."""
        return DAY_SELECTION_MAP.get(self._vehicle_data.get("charge_state", {}).get("preconditioning_times"))

    # ---- Methods -----

    # ---------------- Location ----------------
    def _get_lat_long(self) -> Tuple[Optional[float], Optional[float]]:
        """Get current latitude and longitude."""
        lat = None
        long = None

        if self.native_location_supported:
            long = self.native_longitude
            lat = self.native_latitude
        else:
            long = self.longitude
            lat = self.latitude

        return lat, long

    def update_car_info(self, car: dict) -> None:
        """Update the car info dict from the vehicle_list api."""
        if not car:
            _LOGGER.debug("Attempted to update car id %d with empty car info", self.id)
            return
        if car["vin"] != self.vin:
            _LOGGER.error(
                "Failed updating car info: new VIN (%s) doesn't match existing vin (%s)",
                car["vin"][-5:],
                self.vin[-5:],
            )
            return
        self._car.update(car)

    # --------------- Charging ----------------------

    async def start_charge(self) -> None:
        """Send command to start charge."""
        data = await self._send_command("START_CHARGE")

        if data and data["response"]["result"] is True:
            params = {"charging_state": "Charging"}
            self._vehicle_data["charge_state"].update(params)

    async def stop_charge(self) -> None:
        """Send command to stop charge."""
        # If car is asleep, it's not charging
        data = await self._send_command("STOP_CHARGE", wake_if_asleep=False)

        if data and data["response"]["result"] is True:
            params = {"charging_state": "Stopped"}
            self._vehicle_data["charge_state"].update(params)

    async def change_charge_limit(self, value: float) -> None:
        """Send command to change charge limit."""
        # Only wake car if the value is different
        wake_if_asleep = value != self.charge_limit_soc
        data = await self._send_command(
            "CHANGE_CHARGE_LIMIT", percent=int(value), wake_if_asleep=wake_if_asleep
        )

        if data and data["response"]["result"] is True:
            params = {"charge_limit_soc": int(value)}
            self._vehicle_data["charge_state"].update(params)

    # ------------- Charge Port Door -------------
    # TODO: future scope
    async def charge_port_door_close(self) -> None:
        """Send command to close charge port door."""
        data = await self._send_command("CHARGE_PORT_DOOR_CLOSE")

        if data and data["response"]["result"] is True:
            params = {"charge_port_door_open": False}
            self._vehicle_data["charge_state"].update(params)

    # TODO: future scope
    async def charge_port_door_open(self) -> None:
        """Send command to open charge port door."""
        data = await self._send_command("CHARGE_PORT_DOOR_OPEN")

        if data and data["response"]["result"] is True:
            params = {"charge_port_door_open": True}
            self._vehicle_data["charge_state"].update(params)

    # ----------- Charge Details ------------
    # TODO: future scope
    async def set_charging_amps(self, value: float) -> None:
        """Send command to set charging amps."""
        # Only wake car if the value is different
        wake_if_asleep = value != self._vehicle_data.get("charge_state", {}).get(
            "charge_current_request"
        )
        data = await self._send_command(
            "CHARGING_AMPS", charging_amps=int(value), wake_if_asleep=wake_if_asleep
        )
        # A second API call allows setting below 5 Amps
        if value < 5:
            data = await self._send_command(
                "CHARGING_AMPS", charging_amps=int(value), wake_if_asleep=wake_if_asleep
            )

        if data and data["response"]["result"] is True:
            params = {
                "charge_amps": int(value),
                "charge_current_request": int(value),
            }
            self._vehicle_data["charge_state"].update(params)

    # ----------- Car wakeup state --------------

    # TODO: future scope
    async def wake_up(self) -> None:
        """Send command to wake up."""
        await self._controller.wake_up(car_id=self.id)

    # ----------- scheduled charging ------------

    # TODO: future scope
    async def set_scheduled_charging(self, enable: bool, time: int) -> None:
        """Send command to set scheduled charging time.

        Args
            enable: Turn on (True) or turn off (False) the scheduled charging.
            time: Time in minutes after midnight (local time) to start charging.

        """
        data = await self._send_command("SCHEDULED_CHARGING", enable=enable, time=time)

        if data and data["response"]["result"] is True:
            if enable:
                mode_str = "StartAt"
            else:
                mode_str = "Off"
                time = None
            params = {
                "scheduled_charging_mode": mode_str,
                "scheduled_charging_start_time": time,
                "scheduled_charging_pending": enable,
            }
            self._vehicle_data["charge_state"].update(params)


 #   ------------------- Send Commands | POST -------------------


    async def _send_command(
            self,
            name: str,
            *,
            additional_path_vars: dict = None,
            wake_if_asleep: bool = False,  # May need to be set back to true if we need to wake up the car
            **kwargs,
    ) -> Optional[dict]:
        """Wrap commands sent to Tesla API.

        Args
            name: Name of command to send, from endpoints.json
            additional_path_vars: Additional URI variables ('vehicle_id' already included)
            wake_if_asleep: (default True) Wake car if it's asleep before sending the command
            **kwargs: Any additional parameters for the api call

        """
        path_vars = {"vehicle_id": self.id}
        if additional_path_vars:
            path_vars.update(additional_path_vars)

        _LOGGER.debug("Sending command: %s", name)
        try:
            data = await self._controller.api(
                name, path_vars=path_vars, wake_if_asleep=wake_if_asleep, **kwargs
            )
            _LOGGER.debug("Response from command %s: %s", name, data)
            return data
        # TODO: Needs to be changed to 408 i fixed
        except TeslaException as ex:
            if ex.code == 500 and not wake_if_asleep and not self.is_on:
                # 408 due to being asleep and we didn't try to wake it
                _LOGGER.debug(
                    "Vehicle unavailable for command: %s, car state: %s, wake_if_asleep: %s",
                    name,
                    self.state,
                    wake_if_asleep,
                )
                return None
            raise ex
