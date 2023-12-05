"""Support for Tesla switches."""
import logging

from base import TeslaCarEntity
from const import DOMAIN

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

_LOGGER = logging.getLogger(__name__)
# FeRTIG!!!!!!!!!!!!!


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Tesla switches by config_entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    cars = entry_data["cars"]
    entities = []

    for vin, car in cars.items():
        coordinator = coordinators[vin]
        entities.append(TeslaCarPolling(car, coordinator))
        entities.append(TeslaCarCharger(car, coordinator))

    async_add_entities(entities, update_before_add=True)


class TeslaCarPolling(TeslaCarEntity, SwitchEntity):
    """Representation of a polling switch."""

    type = "polling"
    _attr_icon = "mdi:car-connected"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return True if updates available."""
        controller = self.coordinator.controller
        get_updates = controller.get_updates(vin=self._car.vin)
        if get_updates is None:
            return None
        return bool(get_updates)

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        _LOGGER.debug("Enable polling: %s %s", self.name, self._car.vin)
        self.coordinator.controller.set_updates(vin=self._car.vin, value=True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        _LOGGER.debug("Disable polling: %s %s", self.name, self._car.vin)
        self.coordinator.controller.set_updates(vin=self._car.vin, value=False)
        self.async_write_ha_state()


# TODO:  Most Important!!!!
class TeslaCarCharger(TeslaCarEntity, SwitchEntity):
    """Representation of a Tesla car charger switch."""

    type = "charger"
    _attr_icon = "mdi:ev-station"

    @property
    def is_on(self):
        """Return charging state."""
        return self._car.charging_state == "Charging"

    async def async_turn_on(self, **kwargs):
        """Send the on command."""
        await self._car.start_charge()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send the off command."""
        await self._car.stop_charge()
        self.async_write_ha_state()
