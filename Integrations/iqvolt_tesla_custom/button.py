"""Support for Tesla buttons."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from .tesla_custom_lib.car import TeslaCar

from .base import TeslaCarEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Tesla selects by config_entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    cars = entry_data["cars"]
    entities = []

    for vin, car in cars.items():
        coordinator = coordinators[vin]
        entities.append(TeslaCarWakeUp(car, coordinator))
        entities.append(TeslaCarForceDataUpdate(car, coordinator))

    async_add_entities(entities, update_before_add=True)

# ----------------- May be interesting -----------------
class TeslaCarWakeUp(TeslaCarEntity, ButtonEntity):
    """Representation of a Tesla car wake up button."""

    type = "wake up"
    _attr_icon = "mdi:moon-waning-crescent"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._car.wake_up()

    @property
    def available(self) -> bool:
        """Return True."""
        return True


class TeslaCarForceDataUpdate(TeslaCarEntity, ButtonEntity):
    """Representation of a Tesla car force data update button."""

    type = "force data update"
    _attr_icon = "mdi:database-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.update_controller(wake_if_asleep=True, force=True)

    @property
    def available(self) -> bool:
        """Return True."""
        return True

