"""Select platform for UniFi Network integration.

Support for controlling the load balancing mode of WAN networks.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.networks import Networks
from aiounifi.models.api import ApiItem
from aiounifi.models.network import Network, WanLoadBalanceType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import UnifiEntity, UnifiEntityDescription, async_wan_device_info_fn
from .hub import UnifiHub

PARALLEL_UPDATES = 1

# Load balance type is group membership, the failover priority still decides which
# WAN is active, so a weighted WAN is the primary while it is the only member online.
LOAD_BALANCE_TYPE_TO_OPTION: dict[WanLoadBalanceType, str] = {
    "failover-only": "failover_only",
    "weighted": "weighted",
}
OPTION_TO_LOAD_BALANCE_TYPE: dict[str, WanLoadBalanceType] = {
    option: load_balance_type
    for load_balance_type, option in LOAD_BALANCE_TYPE_TO_OPTION.items()
}


@callback
def async_wan_load_balance_type_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if WAN network reports a load balance type."""
    network = hub.api.networks[obj_id]
    return network.is_wan and network.wan_load_balance_type is not None


@callback
def async_wan_load_balance_type_option_fn(
    hub: UnifiHub, network: Network
) -> str | None:
    """Return current load balance type as an option."""
    if (load_balance_type := network.wan_load_balance_type) is None:
        return None
    return LOAD_BALANCE_TYPE_TO_OPTION.get(load_balance_type)


async def async_wan_load_balance_type_control_fn(
    hub: UnifiHub, obj_id: str, option: str
) -> None:
    """Control load balance type of WAN network."""
    await hub.api.networks.save(
        hub.api.networks[obj_id],
        wan_load_balance_type=OPTION_TO_LOAD_BALANCE_TYPE[option],
    )


@dataclass(frozen=True, kw_only=True)
class UnifiSelectEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    SelectEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi select entity."""

    control_fn: Callable[[UnifiHub, str, str], Coroutine[Any, Any, None]]
    current_option_fn: Callable[[UnifiHub, ApiItemT], str | None]


ENTITY_DESCRIPTIONS: tuple[UnifiSelectEntityDescription, ...] = (
    UnifiSelectEntityDescription[Networks, Network](
        key="WAN load balancing",
        translation_key="wan_load_balancing",
        entity_category=EntityCategory.CONFIG,
        options=list(OPTION_TO_LOAD_BALANCE_TYPE),
        api_handler_fn=lambda api: api.networks,
        control_fn=async_wan_load_balance_type_control_fn,
        current_option_fn=async_wan_load_balance_type_option_fn,
        device_info_fn=async_wan_device_info_fn,
        object_fn=lambda api, obj_id: api.networks[obj_id],
        supported_fn=async_wan_load_balance_type_supported_fn,
        unique_id_fn=lambda hub, obj_id: f"wan_load_balancing-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiSelectEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiSelectEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], SelectEntity
):
    """Base representation of a UniFi select entity."""

    entity_description: UnifiSelectEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            await self.entity_description.control_fn(self.hub, self._obj_id, option)
        except aiounifi.AiounifiException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_request_failed",
            ) from err
        await self.async_refresh_after_control()

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update attr_current_option.
        """
        description = self.entity_description
        self._attr_current_option = description.current_option_fn(
            self.hub, self.get_object()
        )
