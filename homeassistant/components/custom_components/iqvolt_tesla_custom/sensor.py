"""Support for the Tesla sensors."""
## ertig
from datetime import datetime, timedelta
from typing import Optional

from base import TeslaCarEntity
from const import DISTANCE_UNITS_KM_HR, DOMAIN

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    POWER_KILO_WATT,
    SPEED_MILES_PER_HOUR,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import dt
from homeassistant.util.unit_conversion import DistanceConverter

TPMS_SENSORS = {
    "TPMS front left": "tpms_pressure_fl",
    "TPMS front right": "tpms_pressure_fr",
    "TPMS rear left": "tpms_pressure_rl",
    "TPMS rear right": "tpms_pressure_rr",
}

TPMS_SENSOR_ATTR = {
    "TPMS front left": "tpms_last_seen_pressure_time_fl",
    "TPMS front right": "tpms_last_seen_pressure_time_fr",
    "TPMS rear left": "tpms_last_seen_pressure_time_rl",
    "TPMS rear right": "tpms_last_seen_pressure_time_rr",
}


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Tesla Sensors by config_entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    cars = entry_data["cars"]
    entities = []

    for vin, car in cars.items():
        coordinator = coordinators[vin]
        entities.append(TeslaCarBattery(car, coordinator))
        entities.append(TeslaCarChargerRate(car, coordinator))
        entities.append(TeslaCarChargerEnergy(car, coordinator))
        entities.append(TeslaCarChargerPower(car, coordinator))
        entities.append(TeslaCarRange(car, coordinator))
        entities.append(TeslaCarTimeChargeComplete(car, coordinator))
        entities.append(TeslaCarDataUpdateTime(car, coordinator))
    async_add_entities(entities, update_before_add=True)


class TeslaCarBattery(TeslaCarEntity, SensorEntity):
    """Representation of the Tesla car battery sensor."""

    type = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:battery"

    @staticmethod
    def has_battery() -> bool:
        """Return whether the device has a battery."""
        return True

    @property
    def native_value(self) -> int:
        """Return battery level."""
        # usable_battery_level matches the Tesla app and car display
        return self._car.usable_battery_level

    @property
    def icon(self):
        """Return icon for the battery."""
        charging = self._car.charging_state == "Charging"

        return icon_for_battery_level(
            battery_level=self.native_value, charging=charging
        )

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        return {
            "raw_soc": self._car.battery_level,
        }


class TeslaCarChargerEnergy(TeslaCarEntity, SensorEntity):
    """Representation of a Tesla car energy added sensor."""

    type = "energy added"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float:
        """Return the charge energy added."""
        # The car will reset this to 0 automatically when charger
        # goes from disconnected to connected
        return self._car.charge_energy_added

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        if self._car.charge_miles_added_rated:
            added_range = self._car.charge_miles_added_rated
        elif (
            self._car.charge_miles_added_ideal
            and self._car.gui_range_display == "Ideal"
        ):
            added_range = self._car.charge_miles_added_ideal
        else:
            added_range = 0

        if self._car.gui_distance_units == DISTANCE_UNITS_KM_HR:
            added_range = DistanceConverter.convert(
                added_range, LENGTH_MILES, LENGTH_KILOMETERS
            )

        return {
            "added_range": round(added_range, 2),
        }


class TeslaCarChargerPower(TeslaCarEntity, SensorEntity):
    """Representation of a Tesla car charger power."""

    type = "charger power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_KILO_WATT

    @property
    def native_value(self) -> int:
        """Return the charger power."""
        return self._car.charger_power

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        car = self._car
        return {
            "charger_amps_request": car.charge_current_request,
            "charger_amps_actual": car.charger_actual_current,
            "charger_volts": car.charger_voltage,
            "charger_phases": car.charger_phases,
        }


class TeslaCarChargerRate(TeslaCarEntity, SensorEntity):
    """Representation of the Tesla car charging rate."""

    type = "charging rate"
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SPEED_MILES_PER_HOUR
    _attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> float:
        """Return charge rate."""
        charge_rate = self._car.charge_rate

        if charge_rate is None:
            return charge_rate

        return round(charge_rate, 2)

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        return {
            "time_left": self._car.time_to_full_charge,
        }


class TeslaCarRange(TeslaCarEntity, SensorEntity):
    """Representation of the Tesla car range sensor."""

    type = "range"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = LENGTH_MILES
    _attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float:
        """Return range."""
        car = self._car
        range_value = car.battery_range

        if car.gui_range_display == "Ideal":
            range_value = car.ideal_battery_range

        if range_value is None:
            return None

        return round(range_value, 2)

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        # pylint: disable=protected-access
        est_battery_range = self._car._vehicle_data.get("charge_state", {}).get(
            "est_battery_range"
        )
        if est_battery_range is not None:
            est_battery_range_km = DistanceConverter.convert(
                est_battery_range, LENGTH_MILES, LENGTH_KILOMETERS
            )
        else:
            est_battery_range_km = None

        return {
            "est_battery_range_miles": est_battery_range,
            "est_battery_range_km": est_battery_range_km,
        }


class TeslaCarTimeChargeComplete(TeslaCarEntity, SensorEntity):
    """Representation of the Tesla car time charge complete."""

    type = "time charge complete"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-plus"
    _value: Optional[datetime] = None
    _last_known_value: Optional[int] = None
    _last_update_time: Optional[datetime] = None

    @property
    def native_value(self) -> Optional[datetime]:
        """Return time charge complete."""
        if self._car.time_to_full_charge is None:
            charge_hours = 0
        else:
            charge_hours = float(self._car.time_to_full_charge)

        if self._last_known_value != charge_hours:
            self._last_known_value = charge_hours
            self._last_update_time = dt.utcnow()

        if self._car.charging_state == "Charging" and charge_hours > 0:
            new_value = (
                dt.utcnow()
                + timedelta(hours=charge_hours)
                - (dt.utcnow() - self._last_update_time)
            )
            if (
                self._value is None
                or abs((new_value - self._value).total_seconds()) >= 60
            ):
                self._value = new_value
        if self._car.charging_state in ["Charging", "Complete"]:
            return self._value
        return None

    @property
    def extra_state_attributes(self):
        """Return device state attributes."""
        # pylint: disable=protected-access
        minutes_to_full_charge = self._car._vehicle_data.get("charge_state", {}).get(
            "minutes_to_full_charge"
        )

        return {
            "minutes_to_full_charge": minutes_to_full_charge,
        }


# TODO: May be removed
class TeslaCarDataUpdateTime(TeslaCarEntity, SensorEntity):
    """Representation of the TeslajsonPy Last Data Update time."""

    type = "data last update time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:timer"

    @property
    def native_value(self) -> datetime:
        """Return the last data update time."""
        last_time = self.coordinator.controller.get_last_update_time(vin=self._car.vin)
        if not isinstance(last_time, datetime):
            date_obj = datetime.fromtimestamp(last_time, dt.UTC)
        else:
            date_obj = last_time.replace(tzinfo=dt.UTC)
        return date_obj
