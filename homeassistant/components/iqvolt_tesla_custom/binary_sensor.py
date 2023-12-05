"""Support for Tesla binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant

from .base import TeslaCarEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# FERTIG
async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Tesla selects by config_entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    cars = entry_data["cars"]
    entities = []

    for vin, car in cars.items():
        coordinator = coordinators[vin]
        entities.append(TeslaCarOnline(car, coordinator))
        entities.append(TeslaCarChargerConnection(car, coordinator))
        entities.append(TeslaCarCharging(car, coordinator))
        entities.append(TeslaCarScheduledCharging(car, coordinator))
        entities.append(TeslaCarScheduledDeparture(car, coordinator))

    async_add_entities(entities, update_before_add=True)


class TeslaCarChargerConnection(TeslaCarEntity, BinarySensorEntity):
    """Representation of a Tesla car charger connection binary sensor."""

    type = "charger"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    @property
    def is_on(self):
        """Return True if charger connected."""
        return self._car.charging_state != "Disconnected"

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        return {
            "charging_state": self._car.charging_state,
            "conn_charge_cable": self._car.conn_charge_cable,
            "fast_charger_present": self._car.fast_charger_present,
            "fast_charger_brand": self._car.fast_charger_brand,
            "fast_charger_type": self._car.fast_charger_type,
        }


# TODO: Stay
class TeslaCarCharging(TeslaCarEntity, BinarySensorEntity):
    """Representation of Tesla car charging binary sensor."""

    type = "charging"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._car.charging_state == "Charging"


# TODO: Stay
class TeslaCarScheduledCharging(TeslaCarEntity, BinarySensorEntity):
    """Representation of a Tesla car scheduled charging binary sensor."""

    type = "scheduled charging"
    _attr_icon = "mdi:calendar-plus"
    _attr_device_class = None

    @property
    def is_on(self) -> bool:
        """Return True if scheduled charging enabled."""
        return self._car.scheduled_charging_mode == "StartAt"

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        # pylint: disable=protected-access
        timestamp = self._car._vehicle_data.get("charge_state", {}).get(
            "scheduled_charging_start_time"
        )
        return {
            "Scheduled charging time": self._car.scheduled_charging_start_time_app,
            "Scheduled charging timestamp": timestamp,
        }


# -----------------Optional-----------------

# TODO: maybe Stay
class TeslaCarScheduledDeparture(TeslaCarEntity, BinarySensorEntity):
    """Representation of a Tesla car scheduled departure binary sensor."""

    type = "scheduled departure"
    _attr_icon = "mdi:calendar-plus"
    _attr_device_class = None

    @property
    def is_on(self):
        """Return True if scheduled departure enebaled."""
        car = self._car
        return bool(
            car.scheduled_charging_mode == "DepartBy"
            or car.is_preconditioning_enabled
            or car.is_off_peak_charging_enabled
        )

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        # pylint: disable=protected-access
        car = self._car
        timestamp = car._vehicle_data.get("charge_state", {}).get(
            "scheduled_departure_time"
        )
        return {
            "Departure time": car.scheduled_departure_time_minutes,
            "Preconditioning enabled": car.is_preconditioning_enabled,
            "Preconditioning weekdays only": car.is_preconditioning_weekday_only,
            "Off peak charging enabled": car.is_off_peak_charging_enabled,
            "Off peak charging weekdays only": car.is_off_peak_charging_weekday_only,
            "End off peak time": car.off_peak_hours_end_time,
            "Departure timestamp": timestamp,
        }


# TODO: May Stay
class TeslaCarOnline(TeslaCarEntity, BinarySensorEntity):
    """Representation of a Tesla car online binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    type = "online"

    @property
    def is_on(self):
        """Return True if car is online."""
        return self._car.is_on

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        return {
            "vehicle_id": str(self._car.vehicle_id),
            "vin": self._car.vin,
            "id": str(self._car.id),
            "state": self._car.state,
        }
