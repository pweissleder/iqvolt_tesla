"""Support for Tesla numbers."""
from tesla_custom_lib.const import CHARGE_CURRENT_MIN

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import ELECTRIC_CURRENT_AMPERE, PERCENTAGE
from homeassistant.core import HomeAssistant

from .base import TeslaCarEntity
from .const import DOMAIN

# TODO: fertig


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Tesla numbers by config_entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    cars = entry_data["cars"]
    entities = []

    for vin, car in cars.items():
        coordinator = coordinators[vin]
        entities.append(TeslaCarChargeLimit(car, coordinator))
        entities.append(TeslaCarChargingAmps(car, coordinator))

    async_add_entities(entities, update_before_add=True)


class TeslaCarChargeLimit(TeslaCarEntity, NumberEntity):
    """Representation of a Tesla car charge limit number."""

    type = "charge limit"
    _attr_icon = "mdi:ev-station"
    _attr_mode = NumberMode.AUTO
    _attr_native_step = 1

    async def async_set_native_value(self, value: int) -> None:
        """Update charge limit."""
        await self._car.change_charge_limit(value)
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return charge limit."""
        return self._car.charge_limit_soc

    @property
    def native_min_value(self) -> int:
        """Return min charge limit."""
        return (
            self._car.charge_limit_soc_min
            if self._car.charge_limit_soc_min is not None
            else 0
        )

    @property
    def native_max_value(self) -> int:
        """Return max charge limit."""
        return (
            self._car.charge_limit_soc_max
            if self._car.charge_limit_soc_max is not None
            else 100
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return percentage."""
        return PERCENTAGE


class TeslaCarChargingAmps(TeslaCarEntity, NumberEntity):
    """Representation of a Tesla car charging amps number."""

    type = "charging amps"
    _attr_icon = "mdi:ev-station"
    _attr_mode = NumberMode.AUTO
    _attr_native_step = 1

    async def async_set_native_value(self, value: int) -> None:
        """Update charging amps."""
        await self._car.set_charging_amps(value)
        self.async_write_ha_state()

    @property
    def native_value(self) -> int:
        """Return charging amps."""
        return self._car.charge_current_request

    @property
    def native_min_value(self) -> int:
        """Return min charging ampst."""
        return CHARGE_CURRENT_MIN

    @property
    def native_max_value(self) -> int:
        """Return max charging amps."""
        return self._car.charge_current_request_max

    @property
    def native_unit_of_measurement(self) -> str:
        """Return percentage."""
        return ELECTRIC_CURRENT_AMPERE
