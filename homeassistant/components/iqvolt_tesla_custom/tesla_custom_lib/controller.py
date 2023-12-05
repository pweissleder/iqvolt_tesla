#  SPDX-License-Identifier: Apache-2.0
"""
Python Package for controlling Tesla API.

For more details about this api, please refer to the documentation at
https://github.com/zabuldon/teslajsonpy
"""
import asyncio
import logging
import pkgutil
import time
from json import JSONDecodeError
from typing import Dict, List, Optional, Set, Text

import httpx
import orjson
from tenacity import retry, stop_after_delay
from yarl import URL

from .const import *
from .car import TeslaCar
from .connection import Connection

from .exceptions import (
    TeslaException,
    custom_retry,
    custom_retry_except_unavailable,
    custom_wait,
)

_LOGGER = logging.getLogger(__name__)


def valid_result(result):
    """Check if TeslaAPI result successful.

    Parameters
    ----------
    result : tesla API result
        This is the result of a Tesla Rest API call.

    Returns
    -------
    bool
        Tesla API failure can be checked in a dict with a bool in
        ['response']['result'], a bool, or None or
        ['response']['reason'] == 'could_not_wake_buses'
        Returns true when a failure state not detected.

    """
    try:
        return (
                result is not None
                and result is not False
                and (
                        result is True
                        or (
                                isinstance(result, dict)
                                and (
                                        (
                                                isinstance(result["response"], dict)
                                                and (
                                                        result["response"].get("result") is True
                                                        or result["response"].get("reason")
                                                        != "could_not_wake_buses"
                                                )
                                        )
                                        or isinstance(result.get("response"), list)
                                )
                        )
                )
        )
    except TypeError as exception:
        _LOGGER.error("Result: %s, %s", result, exception)
        return False


class Controller:
    #  pylint: disable=too-many-public-methods
    """Controller for connections to Tesla Motors API."""

    def __init__(
            self,
            websession: Optional[httpx.AsyncClient] = None,
            wrapper_api_key: Text = None,
            base_url: Text = BASE_URL,
            polling_policy: Text = None,
    ) -> None:
        """Initialize controller.

        Args:
            websession (aiohttp.ClientSession): Websession for aiohttp.
            email (Text, optional): Email account. Defaults to None.
            password (Text, optional): Password. Defaults to None.
            access_token (Text, optional): Access token. Defaults to None.
            refresh_token (Text, optional): Refresh token. Defaults to None.
            expiration (int, optional): Timestamp when access_token expires. Defaults to 0
            update_interval (int, optional): Seconds between allowed updates to the API.  This is to prevent
            being blocked by Tesla. Defaults to UPDATE_INTERVAL.
            enable_websocket (bool, optional): Whether to connect with websockets. Defaults to False.
            polling_policy (Text, optional): How aggressively will we poll the car. Possible values:
            Not set - Only keep the car awake while it is actively charging or driving, and while sentry
            mode is enabled (default).
            'connected' - Also keep the car awake while it is connected to a charger, even if the charging
            session is complete.
            'always' - Keep polling the car at all times.  Will possibly never allow the car to sleep.
            auth_domain (str, optional): The authentication domain. Defaults to const.AUTH_DOMAIN

        """

        self.__connection = Connection(
            websession=websession
            if websession and isinstance(websession, httpx.AsyncClient)
            else httpx.AsyncClient(timeout=60),
            wrapper_api_key=wrapper_api_key,
            base_url= base_url,
            polling_policy =polling_policy

        )
        self._update_interval: int = UPDATE_INTERVAL
        self.__update = {}
        self._last_update_time = {}  # succesful update attempts by car
        self._last_wake_up_time = {}  # succesful wake_ups by car
        self._last_attempted_update_time = 0  # all attempts by controller
        self.__lock = {}
        self.__update_lock = None  # controls access to update function
        self.__wakeup_lock = {}
        self.car_online = {}
        self.__id_vin_map = {}
        self.__vin_id_map = {}
        self.__vin_vehicle_id_map = {}
        self.__vehicle_id_vin_map = {}
        self.__last_parked_timestamp = {}
        self._update_interval_vin = {}
        self.__update_state = {}

        self.endpoints = {}
        self.polling_policy = polling_policy

        self._vehicle_list: dict[dict] = []  # List of vehicles as the response value
        self._vehicle_data: dict[str, dict] = {}  # Dict[vin, vehicle_data]
        self.cars: dict[str, TeslaCar] = {}  # Dict[vin, TeslaCar]

    async def connect(
            self,
            include_vehicles: bool = True,
    ) -> dict[Text, Text]:
        """Connect controller to Tesla.

        Args
            test_login (bool, optional): Whether to test credentials only. Defaults to False.
            include_vehicles (bool, optional): Whether to include vehicles. Defaults to True.
            include_energysites(bool, optional): Whether to include energysites. Defaults to True.
            mfa_code (Text, optional): MFA code to use for connection

        Returns
            Dict[Text, Text]: Returns the refresh_token, access_token, id_token and expires_in time

        """
        self._last_attempted_update_time = round(time.time())
        self.__update_lock = asyncio.Lock()

        _LOGGER.debug("Controller connects to the get_vehicles Endpoint")

        self._vehicle_list = [
            cars for cars in  await self.get_vehicles() if "vehicle_id" in cars
        ]
        _LOGGER.debug("Controller updated cars")
        return {
            "Authorization": self.__connection.wrapper_api_key,
        }

    async def disconnect(self) -> None:
        """Disconnect from Tesla api."""
        _LOGGER.debug("Disconnecting controller")
        await self.__connection.close()

    # TODO: Stay
    async def get_vehicles(self) -> list:
        """Get vehicles json from TeslaAPI."""
        return (await self.api("VEHICLE_LIST"))["response"]

    async def get_vehicle_data(self, vin: str, wake_if_asleep: bool = False) -> dict:
        """Get vehicle data json from TeslaAPI for a given vin."""
        try:
            response = (
                await self.api(
                    "VEHICLE_DATA",
                    path_vars={"vehicle_id": self._vin_to_id(vin)},
                    wake_if_asleep=wake_if_asleep,
                )
            )["response"]

        except TeslaException as ex:
            if ex.message == "VEHICLE_UNAVAILABLE":
                _LOGGER.debug("Vehicle offline - data unavailable")
                return {}
            raise ex

        return response

    async def get_vehicle_summary(self, vin: str) -> dict:
        """Get vehicle summary json from TeslaAPI for a given vin."""
        return (
            await self.api(
                "VEHICLE_SUMMARY",
                path_vars={"vehicle_id": self._vin_to_id(vin)},
                wake_if_asleep=False,
            )
        )["response"]

    async def generate_car_objects(
            self,
            wake_if_asleep: bool = False,
            filtered_vins: Optional[list[Text]] = None,
    ) -> dict[str, TeslaCar]:
        """Generate car objects.

        Args
            wake_if_asleep (bool, optional): Wake up vehicles if asleep.
            filtered_vins (list, optional): If not empty, filters the cars by the provided VINs.

        """
        for car in self._vehicle_list:
            vin = car["vin"]
            if filtered_vins and vin not in filtered_vins:
                _LOGGER.debug("Skipping car with VIN: %s", vin)
                continue

            self.set_id_vin(car_id=car["id"], vin=vin)
            self.set_vehicle_id_vin(vehicle_id=car["vehicle_id"], vin=vin)
            self.__lock[vin] = asyncio.Lock()
            self.__wakeup_lock[vin] = asyncio.Lock()
            self._last_update_time[vin] = 0
            self._last_wake_up_time[vin] = 0
            self.__update[vin] = True
            self.__update_state[vin] = "normal"
            self.set_car_online(vin=vin, online_status=car["state"] == "online")
            self.set_last_park_time(vin=vin, timestamp=self._last_attempted_update_time)
            self._vehicle_data[vin] = {}

            try:
                self._vehicle_data[vin] = await self.get_vehicle_data(
                    vin, wake_if_asleep=wake_if_asleep
                )
            except TeslaException as ex:
                _LOGGER.warning(
                    "Unable to get vehicle data during setup, car will still be added. %s: %s",
                    ex.code,
                    ex.message,
                )
            self.cars[vin] = TeslaCar(car, self, self._vehicle_data[vin])

        return self.cars

    # TODO: future scope
    async def wake_up(self, car_id) -> bool:
        """Attempt to wake the car, returns True if successfully awakened."""
        car_vin = self._id_to_vin(car_id)
        car_id = self._update_id(car_id)
        async with self.__wakeup_lock[car_vin]:
            wake_start_time = time.time()
            wake_deadline = wake_start_time + WAKE_TIMEOUT
            _LOGGER.debug(
                "%s: Sending wake request with deadline of: %d",
                car_vin[-5:],
                wake_deadline,
            )
            result = await self.api(
                "WAKE_UP", path_vars={"vehicle_id": car_id}, wake_if_asleep=False
            )
            state = result.get("response", {}).get("state")
            self.set_car_online(
                car_id=car_id,
                online_status=state == "online",
            )
            while not self.is_car_online(vin=car_vin) and time.time() < wake_deadline:
                await asyncio.sleep(WAKE_CHECK_INTERVAL)
                response = await self.get_vehicle_summary(vin=car_vin)
                state = response.get("state")
                self.set_car_online(
                    car_id=car_id,
                    online_status=state == "online",
                )

            _LOGGER.debug(
                "%s: Wakeup took %d seconds, state: %s",
                car_vin[-5:],
                time.time() - wake_start_time,
                state,
            )
            return self.is_car_online(vin=car_vin)

    async def update(
            self,
            car_id: Optional[Text] = None,
            wake_if_asleep: bool = False,
            force: bool = False,
            update_vehicles: bool = True,
            vins: Optional[set[str]] = None,
    ) -> bool:
        #  pylint: disable=too-many-locals,too-many-statements
        """Update all vehicle and energy site attributes in the cache.

        This command will connect to the Tesla API and first update the list of
        online vehicles assuming no attempt for at least the [update_interval].
        It will then update all the cached values for cars that are awake
        assuming no update has occurred for at least the [update_interval].

        For energy sites, they will only be updated if car_id is blank.

        Args
            car_id (Text, optional): The vehicle to update. If None, all cars are updated. Defaults to None.
            wake_if_asleep (bool, optional): force a vehicle awake. Defaults to False.
            force (bool, optional): force a vehicle update regardless of the update_interval. Defaults to False.
            vins: (Set[str], optional): The cars to update. If None, all cars are updated. Defaults to None.
            energy_site_ids: (Set[str], optional): The energy sites to update. If None, all sites are updated. Defaults to None.

        Returns
            Whether update was successful.

        """
        tasks = []


# Potential Problems with update time as formula to calculate the next update was removed
        async def _get_and_process_car_data(vin: str) -> None:
            async with self.__lock[vin]:
                _LOGGER.debug("%s: Updating VEHICLE_DATA", vin[-5:])
                try:
                    response = await self.get_vehicle_data(
                        vin, wake_if_asleep=wake_if_asleep
                    )
                except TeslaException as ex:
                    # VEHICLE_UNAVAILABLE is handled in get_vehicle_data as debug and ignore
                    # Anything else would be caught here and logged as a warning
                    _LOGGER.warning(
                        "Unable to get vehicle data during poll. %s: %s",
                        ex.code,
                        ex.message,
                    )
                    response = None

                if response:
                    self._last_update_time[vin] = round(time.time())
                    self._vehicle_data[vin].update(response)

        async with self.__update_lock:
            if self._vehicle_list:
                cur_time = round(time.time())
                #  Update the online cars using get_vehicles()
                last_update = self._last_attempted_update_time
                _LOGGER.debug(
                    "Get vehicles. Force: %s Time: %s Interval %s",
                    force,
                    cur_time - last_update,
                    ONLINE_INTERVAL,
                )
                if (
                        force
                        or cur_time - last_update >= ONLINE_INTERVAL
                        and update_vehicles
                ):
                    cars = await self.get_vehicles()
                    for car in cars:
                        self.set_id_vin(car_id=car["id"], vin=car["vin"])
                        self.set_vehicle_id_vin(
                            vehicle_id=car["vehicle_id"], vin=car["vin"]
                        )
                        self.set_car_online(
                            vin=car["vin"], online_status=car["state"] == "online"
                        )
                        self.cars[car["vin"]].update_car_info(car)
                    self._last_attempted_update_time = cur_time

                # Only update online vehicles that haven't been updated recently
                # The throttling is per car's last succesful update
                # Note: This separate check is because there may be individual cars
                # to update.
                car_id = self._update_id(car_id)
                car_vin = self._id_to_vin(car_id)

                for vin, online in self.get_car_online().items():
                    # If specific car_id provided, only update match
                    if (
                            (car_vin and car_vin != vin)
                            or vin not in self.__lock
                    ):
                        continue

                    if isinstance(vins, set) and vin not in vins:
                        continue

                    async with self.__lock[vin]:
                        if (
                                (
                                        online
                                        or (
                                                wake_if_asleep
                                                and self.cars[vin].state in ["asleep", "offline"]
                                        )
                                )
                                and (  # pylint: disable=too-many-boolean-expressions
                                self.__update.get(vin)
                        )  # Only update cars with update flag on
                                and (
                                force
                                or vin not in self._last_update_time
                                or (
                                        cur_time - self._last_update_time[vin]
                                        >= UPDATE_INTERVAL
                                )
                        )
                        ):
                            tasks.append(_get_and_process_car_data(vin))
                        else:
                            _LOGGER.debug(
                                (
                                    "%s: Skipping update with state %s. Polling: %s. "
                                    "Last update: %s ago. Last parked: %s ago. "
                                    "Last wake up %s ago. "
                                ),
                                vin[-5:],
                                self.cars[vin].state,
                                self.__update.get(vin),
                                cur_time - self._last_update_time[vin],
                                cur_time - self.get_last_park_time(vin=vin),
                                cur_time - self.get_last_wake_up_time(vin=vin),
                            )

            return any(await asyncio.gather(*tasks))

    def get_updates(self, car_id: Text = None, vin: Text = None):
        """Get updates dictionary.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. It is the id
            field for identifying the car across the owner-api endpoint.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
        vin : string
            VIN number.

        If both car_id and vin is provided. VIN overrides car_id.

        Returns
        -------
        bool or dict of booleans
            If car_id or vin exists, a bool indicating whether updates should be
            processed. Othewise, the entire updates dictionary.

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and vin in self.__update:
            return self.__update[vin]
        return self.__update

    def set_updates(
            self, car_id: Text = None, vin: Text = None, value: bool = False
    ) -> None:
        """Set updates dictionary.

        If a vehicle is enabled, the vehicle will force an update on next poll.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. Confusingly it
            is not the vehicle_id field for identifying the car across
            different endpoints.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
        vin : string
            Vin number
        value : bool
            Whether the specific car_id should be updated.

        Returns
        -------
        None

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin:
            self.__update[vin] = value
            if self.__update[vin]:
                self.set_last_update_time(vin=vin)
                _LOGGER.debug(
                    "%s: Set Updates enabled; forcing update on next poll by resetting last_update_time",
                    vin[-5:],
                )

    def get_last_update_time(self, car_id: Text = None, vin: Text = None):
        """Get last_update time dictionary.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. It is the id
            field for identifying the car across the owner-api endpoint.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
            If no car_id, returns the complete dictionary.
        vin : string
            Vin number

        Returns
        -------
        int or dict of ints
            If car_id exists, a int (time.time()) indicating when updates last
            processed. Othewise, the entire updates dictionary.

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and vin in self._last_update_time:
            return self._last_update_time[vin]
        return self._last_update_time

    def set_last_update_time(
            self, car_id: Text = None, vin: Text = None, timestamp: float = 0
    ) -> None:
        """Set updated_time for car_id."""
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin:
            self._last_update_time[vin] = timestamp

    def get_last_park_time(self, car_id: Text = None, vin: Text = None):
        """Get park_time.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. It is the id
            field for identifying the car across the owner-api endpoint.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
            If no car_id, returns the complete dictionary.
        vin : string
            Vin number

        Returns
        -------
        int or dict of ints
            If car_id exists, a int (time.time()) indicating when car was last
            parked. Othewise, the entire updates dictionary.

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and vin in self.__last_parked_timestamp:
            return self.__last_parked_timestamp[vin]
        return self.__last_parked_timestamp

    def set_last_park_time(
            self,
            car_id: Text = None,
            vin: Text = None,
            timestamp: float = 0,
            shift_state: Text = None,
    ) -> None:
        """Set park_time for car_id."""
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin:
            _LOGGER.debug(
                "%s: Resetting last_parked_timestamp to: %s shift_state %s",
                vin[-5:],
                timestamp,
                shift_state,
            )
            self.__last_parked_timestamp[vin] = timestamp

    def get_last_wake_up_time(self, car_id: Text = None, vin: Text = None):
        """Get wakeup_time.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. It is the id
            field for identifying the car across the owner-api endpoint.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
            If no car_id, returns the complete dictionary.
        vin : string
            VIN number

        Returns
        -------
        int or dict of ints
            If car_id exists, a int (time.time()) indicating when car was last
            waken up. Othewise, the entire updates dictionary.

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and vin in self._last_wake_up_time:
            return self._last_wake_up_time[vin]
        return self._last_wake_up_time

    def set_last_wake_up_time(
            self, car_id: Text = None, vin: Text = None, timestamp: float = 0
    ) -> None:
        """Set wakeup_time for car_id."""
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin:
            _LOGGER.debug("%s: Resetting last_wake_up_time to: %s", vin[-5:], timestamp)
            self._last_wake_up_time[vin] = timestamp

    def set_car_online(
            self, car_id: Text = None, vin: Text = None, online_status: bool = True
    ) -> None:
        """Set online status for car_id.

        Will also update "last_wake_up_time" if the car changes from offline
        to online

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint.
        vin : string
            VIN number

        online_status : boolean
            True if the car is online (awake)
            False if the car is offline (out of reach or sleeping)


        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and self.get_car_online(vin=vin) != online_status:
            _LOGGER.debug(
                "%s: Changing car_online from %s to %s",
                vin[-5:],
                self.get_car_online(vin=vin),
                online_status,
            )
            self.car_online[vin] = online_status
            if online_status:
                self.set_last_wake_up_time(vin=vin, timestamp=round(time.time()))

    def get_car_online(self, car_id: Text = None, vin: Text = None):
        """Get online status for car_id or all cars.

        Parameters
        ----------
        car_id : string
            Identifier for the car on the owner-api endpoint. It is the id
            field for identifying the car across the owner-api endpoint.
            https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
        vin : string
            VIN number.

        If both car_id and vin is provided. VIN overrides car_id.

        Returns
        -------
        dict or boolean
            If car_id or vin exists, a boolean with the online status for a
            single car.
            Othewise, the entire dictionary with all cars.

        """
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin and vin in self.car_online:
            return self.car_online[vin]
        return self.car_online

    def is_car_online(self, car_id: Text = None, vin: Text = None) -> bool:
        """Alias for get_car_online for better readability."""
        return self.get_car_online(car_id=car_id, vin=vin)

    def set_id_vin(self, car_id: Text, vin: Text) -> None:
        """Update mappings of car_id <--> vin."""
        car_id = str(car_id)
        self.__id_vin_map[car_id] = vin
        self.__vin_id_map[vin] = car_id

    def set_vehicle_id_vin(self, vehicle_id: Text, vin: Text) -> None:
        """Update mappings of vehicle_id <--> vin."""
        vehicle_id = str(vehicle_id)
        self.__vehicle_id_vin_map[vehicle_id] = vin
        self.__vin_vehicle_id_map[vin] = vehicle_id

    @property
    def update_interval(self) -> int:
        """Return update_interval.

        Returns
            int: The number of seconds between updates

        """
        return self._update_interval

    @update_interval.setter
    def update_interval(self, value: int) -> None:
        """Set update_interval."""
        # Sometimes receive a value of None
        if value and value < 0:
            value = UPDATE_INTERVAL
        if value and value:
            _LOGGER.debug("Update interval set to %s", value)
            self._update_interval = int(value)

    def set_update_interval_vin(
            self, car_id: Text = None, vin: Text = None, value: int = None
    ) -> None:
        """Set update interval for specific vin."""

        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin is None:
            return
        if value is None or value < 0:
            _LOGGER.debug("%s: Update interval reset to default", vin[-5:])
            self._update_interval_vin.pop(vin, None)
        else:
            _LOGGER.debug("%s: Update interval set to %s", vin[-5:], value)
            self._update_interval_vin.update({vin: value})

    def get_update_interval_vin(self, car_id: Text = None, vin: Text = None) -> int:
        """Get update interval for specific vin or default if no vin specific."""
        if car_id and not vin:
            vin = self._id_to_vin(car_id)
        if vin is None or vin == "":
            return self.update_interval

        return self._update_interval_vin.get(vin, self.update_interval)

    def _id_to_vin(self, car_id: Text) -> Optional[Text]:
        """Return vin for a car_id."""
        return self.__id_vin_map.get(str(car_id))

    def _vin_to_id(self, vin: Text) -> Optional[Text]:
        """Return car_id for a vin."""
        return self.__vin_id_map.get(vin)

    def _vehicle_id_to_vin(self, vehicle_id: Text) -> Optional[Text]:
        """Return vin for a vehicle_id."""
        return self.__vehicle_id_vin_map.get(vehicle_id)

    def _vehicle_id_to_id(self, vehicle_id: Text) -> Optional[Text]:
        """Return car_id for a vehicle_id."""
        return self._vin_to_id(self._vehicle_id_to_vin(vehicle_id))

    def vin_to_vehicle_id(self, vin: Text) -> Optional[Text]:
        """Return vehicle_id for a vin."""
        return self.__vin_vehicle_id_map.get(vin)

    def _update_id(self, car_id: Text) -> Optional[Text]:
        """Update the car_id for a vin."""
        new_car_id = self.__vin_id_map.get(self._id_to_vin(car_id))
        if new_car_id:
            car_id = new_car_id
        return car_id


    async def api(
            self,
            name: str,
            path_vars=None,
            wake_if_asleep: bool = False,
            **kwargs,
    ):
        """Perform api request for given endpoint name, with keyword arguments as parameters.

        Code from https://github.com/tdorssers/TeslaPy/blob/master/teslapy/__init__.py#L242-L277 under MIT

        Parameters
        ----------
        name : string
            Endpoint command, e.g., STATUS. See https://github.com/zabuldon/teslajsonpy/blob/dev/teslajsonpy/endpoints.json
        path_vars : dict
            Path variables to be replaced. Defaults to None. For vehicle_id reference see https://tesla-api.timdorr.com/api-basics/vehicles#vehicle_id-vs-id
        wake_if_asleep : bool
            If a sleeping vehicle should be woken before making the api call.
        **kwargs :
            Arguments to pass to underlying Tesla command. See https://tesla-api.timdorr.com/vehicle/commands

        Raises
        ------
        ValueError:
            If endpoint name is not found
        NotImplementedError:
            Endpoint method not implemented
        ValueError:
            Path variables missing

        Returns
        -------
        dict
            Tesla json response object.

        """
        path_vars = path_vars or {}
        # Load API endpoints once
        if not self.endpoints:
            try:
                data = pkgutil.get_data(__name__, "endpoints.json")
                self.endpoints = orjson.loads(  # pylint: disable=no-member
                    data.decode()
                )
                _LOGGER.debug("%d endpoints loaded", len(self.endpoints))
            except (IOError, ValueError, JSONDecodeError):
                _LOGGER.error("No endpoints loaded")
        # Lookup endpoint name
        try:
            endpoint = self.endpoints[name]
        except KeyError as ex:
            raise ValueError("Unknown endpoint name " + name) from ex
        # Only JSON is supported
        if endpoint.get("CONTENT", "JSON") != "JSON" or name == "STATUS":
            raise NotImplementedError(f"Endpoint {name} not implemented")
        # Substitute path variables in URI
        try:
            uri = endpoint["URI"].format(**path_vars)
        except KeyError as ex:
            raise ValueError(f"{name} requires path variable {ex}") from ex
        method = endpoint["TYPE"].lower()

        # Old @wake_up decorator condensed here
        if wake_if_asleep:
            car_id = path_vars.get("vehicle_id")
            if not car_id:
                raise ValueError(
                    "wake_if_asleep only supported on endpoints with 'vehicle_id' path variable"
                )
            # If we already know the car is asleep, go ahead and wake it
            if not self.is_car_online(car_id=car_id):
                await self.wake_up(car_id=car_id)
                return await self.__post_with_retries(
                    "", method=method, data=kwargs, url=uri
                )

            # We think the car is awake, lets try the api call:
            try:
                response = await self.__post_with_retries(
                    "", method=method, data=kwargs, url=uri
                )
            except TeslaException as ex:
                # Don't bother to wake and retry if it's not retryable
                if not ex.retryable:
                    raise ex
                response = None
            # It may fail if the car slept since the last api update
            if not valid_result(response):
                # Assumed it failed because it was asleep and we didn't know it
                await self.wake_up(car_id=car_id)
                response = await self.__post_with_retries(
                    "", method=method, data=kwargs, url=uri
                )
            return response

        # Perform request using given keyword arguments as parameters
        # wake_if_asleep is False so we do not retry if the car is asleep
        # or if the car is unavailable
        return await self.__post_with_retries_except_unavailable(
            "", method=method, data=kwargs, url=uri
        )

    @retry(
        wait=custom_wait,
        retry=custom_retry,
        stop=stop_after_delay(MAX_API_RETRY_TIME),
        reraise=True,
    )
    async def __post_with_retries(self, command, method="post", data=None, url=""):
        """Call connection.post with retries for common exceptions.

        Retries if the car is unavailable.
        """
        return await self.__connection.post(command, method=method, data=data, url=url)

    @retry(
        wait=custom_wait,
        retry=custom_retry_except_unavailable,
        stop=stop_after_delay(MAX_API_RETRY_TIME),
        reraise=True,
    )
    async def __post_with_retries_except_unavailable(
            self, command, method="post", data=None, url=""
    ):
        """Call connection.post with retries for common exceptions.

        Does not retry if the car is unavailable. This should be
        used when wake_if_asleep is False since its unlikely the
        car will suddenly become available if its offline/sleep.
        """
        return await self.__connection.post(command, method=method, data=data, url=url)
