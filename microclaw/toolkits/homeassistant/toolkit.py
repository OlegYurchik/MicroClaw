from typing import Any

from homeassistant_api import Client
from homeassistant_api.models import (
    Entity as HAEntity,
    Service as HAService,
    State as HAState,
)
from homeassistant_api.models.states import Context as HAContext

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.settings import ToolKitSettings
from .dto import (
    Context,
    Entity,
    Service,
    State,
)
from .settings import HomeAssistantSettings


class HomeAssistantToolKit(BaseToolKit[HomeAssistantSettings]):
    """
    Tools for controlling and monitoring Home Assistant entities, services, areas, and
    devices.
    """

    def __init__(self, settings: ToolKitSettings):
        super().__init__(settings=settings)
        self._client = None

    async def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(
                api_url=self.settings.url,
                token=self.settings.token,
                use_async=True,
                verify_ssl=self.settings.verify_ssl,
            )
        return self._client

    @tool
    async def get_services(self) -> list[Service]:
        """
        Get all available services from Home Assistant.

        Returns:
            List of Service objects with their descriptions and fields
        """
        client = await self._get_client()
        ha_domains = await client.async_get_domains()
        services = []
        for domain_name, ha_domain in ha_domains.items():
            for service_name, ha_service in ha_domain.services.items():
                services.append(self._convert_service(ha_service=ha_service))
        return services

    @tool
    async def get_entities(self, domain: str | None = None) -> list[Entity]:
        """
        Get entities from Home Assistant.

        NOTE: This method can return a large number of entities. For better performance,
        use get_entity() for a specific entity or search_entities() for filtered results.

        Args:
            domain: Optional domain filter (e.g., 'light', 'switch', 'sensor').
                    If None, returns all entities (can be very large).

        Returns:
            List of Entity objects with their current states and attributes
        """
        client = await self._get_client()
        ha_entities_groups = await client.async_get_entities()
        entities = []
        for ha_entity_group in ha_entities_groups.values():
            for ha_entity in ha_entity_group.entities.values():
                if domain is None or ha_entity.entity_id.startswith(f"{domain}."):
                    entities.append(self._convert_entity(ha_entity=ha_entity))
        return entities

    @tool
    async def get_entity(self, entity_id: str) -> Entity:
        """
        Get a specific entity by its ID.

        Args:
            entity_id: Entity identifier (e.g., light.living_room)

        Returns:
            Entity object with current state and attributes
        """
        client = await self._get_client()
        ha_entity = await client.async_get_entity(entity_id=entity_id)
        return self._convert_entity(ha_entity=ha_entity)

    @tool
    async def get_state(self, entity_id: str) -> State:
        """
        Get the current state of an entity.

        Args:
            entity_id: Entity identifier (e.g., light.living_room)

        Returns:
            State object with current state value and attributes
        """
        client = await self._get_client()
        ha_state = await client.async_get_state(entity_id=entity_id)
        return self._convert_state(ha_state)

    @tool
    async def search_entities(self, pattern: str, domain: str | None = None) -> list[Entity]:
        """
        Search for entities by name pattern.

        This is more efficient than get_entities() when you need to find specific entities.
        Use this method to discover entity IDs before controlling them.

        Args:
            pattern: Search pattern (e.g., 'boiler', 'light.kitchen', 'living')
            domain: Optional domain filter (e.g., 'light', 'switch', 'sensor')

        Returns:
            List of matching Entity objects
        """
        client = await self._get_client()
        ha_entities_groups = await client.async_get_entities()
        entities = []
        pattern_lower = pattern.lower()
        for ha_entity_group in ha_entities_groups.values():
            for ha_entity in ha_entity_group.entities.values():
                entity_id = ha_entity.entity_id
                if domain is not None and not entity_id.startswith(f"{domain}."):
                    continue
                if (pattern_lower in entity_id.lower() or
                    (ha_entity.slug and pattern_lower in ha_entity.slug.lower())):
                    entities.append(self._convert_entity(ha_entity=ha_entity))
        return entities

    @tool
    async def turn_on(self, entity_id: str, **kwargs: Any) -> str:
        """
        Turn on an entity (light, switch, etc.).

        This is the preferred method for controlling devices. For lights, you can pass
        brightness (0-255), color_temp, rgb_color, etc. as kwargs.

        Args:
            entity_id: Entity identifier (e.g., light.living_room, switch.water_boiler)
            **kwargs: Additional service parameters (e.g., brightness=255, color_temp=400)
        """
        domain = entity_id.split(".")[0]
        await self.call_service(
            domain=domain,
            service="turn_on",
            entity_id=entity_id,
            service_data=kwargs,
        )

    @tool
    async def turn_off(self, entity_id: str) -> str:
        """
        Turn off an entity (light, switch, etc.).

        Args:
            entity_id: Entity identifier (e.g., light.living_room, switch.water_boiler)
        """
        domain = entity_id.split(".")[0]
        await self.call_service(
            domain=domain,
            service="turn_off",
            entity_id=entity_id,
        )

    @tool
    async def toggle(self, entity_id: str) -> str:
        """
        Toggle an entity (light, switch, etc.).

        Args:
            entity_id: Entity identifier (e.g., light.living_room, switch.water_boiler)
        """
        domain = entity_id.split(".")[0]
        await self.call_service(
            domain=domain,
            service="toggle",
            entity_id=entity_id,
        )

    @tool
    async def call_service(
            self,
            domain: str,
            service: str,
            service_data: dict[str, Any] | None = None,
            entity_id: str | None = None,
    ) -> str:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g., light, switch, script)
            service: Service name (e.g., turn_on, turn_off)
            service_data: Optional service parameters
            entity_id: Optional entity ID to target
        """
        if entity_id:
            service_data = service_data or {}
            service_data["entity_id"] = entity_id

        client = await self._get_client()
        await client.async_trigger_service(
            domain=domain,
            service=service,
            **(service_data or {}),
        )

    def _convert_entity(self, ha_entity: HAEntity) -> Entity:
        return Entity(
            entity_id=ha_entity.entity_id,
            slug=ha_entity.slug,
            domain=ha_entity.entity_id.split(".")[0],
            state=self._convert_state(ha_entity.state) if ha_entity.state else None,
        )

    def _convert_state(self, ha_state: HAState) -> State:
        return State(
            entity_id=ha_state.entity_id,
            state=ha_state.state,
            attributes=ha_state.attributes,
            last_changed=ha_state.last_changed,
            last_updated=ha_state.last_updated,
            last_reported=ha_state.last_reported,
            context=self._convert_context(ha_state.context) if ha_state.context else None,
        )

    def _convert_context(self, ha_context: HAContext) -> Context:
        return Context(
            id=ha_context.id,
            parent_id=ha_context.parent_id,
            user_id=ha_context.user_id,
        )

    def _convert_service(self, ha_service: HAService) -> Service:
        return Service(
            domain=ha_service.domain.domain_id,
            service_id=ha_service.service_id,
            name=ha_service.name,
            description=ha_service.description,
            fields=self._convert_service_fields(ha_service.fields) if ha_service.fields else {},
            target=self._convert_service_target(ha_service.target) if ha_service.target else None,
            response=self._convert_service_response(ha_service.response) if ha_service.response else None,
        )

    def _convert_service_fields(self, ha_fields: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, field in ha_fields.items():
            if hasattr(field, "model_dump"):
                result[key] = field.model_dump()
            elif hasattr(field, "dict"):
                result[key] = field.dict()
            else:
                result[key] = field
        return result

    def _convert_service_target(self, ha_target: Any) -> dict[str, Any]:
        """Convert homeassistant_api service target to dict."""
        if hasattr(ha_target, "model_dump"):
            return ha_target.model_dump()
        elif hasattr(ha_target, "dict"):
            return ha_target.dict()
        return ha_target

    def _convert_service_response(self, ha_response: Any) -> dict[str, Any]:
        """Convert homeassistant_api service response to dict."""
        if hasattr(ha_response, "model_dump"):
            return ha_response.model_dump()
        elif hasattr(ha_response, "dict"):
            return ha_response.dict()
        return ha_response
