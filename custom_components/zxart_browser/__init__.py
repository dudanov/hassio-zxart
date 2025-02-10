"""The ZXArt Browser integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from zxart import ZXArtClient

type ZXArtConfigEntry = ConfigEntry[ZXArtClient]


async def async_setup_entry(hass: HomeAssistant, entry: ZXArtConfigEntry) -> bool:
    """Set up ZXArt Browser from a config entry.

    This integration doesn't set up any entities, as it provides a media source
    only.
    """
    session = async_get_clientsession(hass)
    entry.runtime_data = ZXArtClient(session=session)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
