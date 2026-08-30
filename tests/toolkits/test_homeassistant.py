from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.homeassistant.toolkit import HomeAssistantToolKit


class TestHomeAssistantToolKit:
    @pytest.fixture
    def mock_ha_client(self):
        client = MagicMock()
        client.async_get_domains = AsyncMock(return_value={})
        client.async_get_entities = AsyncMock(return_value={})
        client.async_get_entity = AsyncMock(
            return_value=MagicMock(
                entity_id="light.living_room",
                slug="living_room",
                state=MagicMock(
                    entity_id="light.living_room",
                    state="on",
                    attributes={},
                    last_changed=None,
                    last_updated=None,
                    last_reported=None,
                    context=None,
                ),
            )
        )
        client.async_get_state = AsyncMock(
            return_value=MagicMock(
                entity_id="light.living_room",
                state="on",
                attributes={},
                last_changed=None,
                last_updated=None,
                last_reported=None,
                context=None,
            )
        )
        client.async_trigger_service = AsyncMock()
        return client

    @pytest.fixture
    def toolkit(self, mock_ha_client):
        settings = ToolKitSettings(
            path="microclaw.toolkits.homeassistant.toolkit.HomeAssistantToolKit",
            args={"url": "http://ha:8123", "token": "token"},
        )
        return HomeAssistantToolKit(key="ha", settings=settings, client=mock_ha_client)

    @pytest.mark.asyncio
    async def test_list_states_success(self, toolkit, mock_ha_client):
        mock_ha_client.async_get_entities = AsyncMock(
            return_value={
                "light": MagicMock(
                    entities={
                        "light.living_room": MagicMock(
                            entity_id="light.living_room",
                            slug="living_room",
                            state=MagicMock(
                                entity_id="light.living_room",
                                state="on",
                                attributes={},
                                last_changed=None,
                                last_updated=None,
                                last_reported=None,
                                context=None,
                            ),
                        )
                    }
                )
            }
        )
        result = await toolkit.get_entities()
        assert len(result) == 1
        assert result[0].entity_id == "light.living_room"

    @pytest.mark.asyncio
    async def test_get_state_success(self, toolkit):
        result = await toolkit.get_state("light.living_room")
        assert result.entity_id == "light.living_room"

    @pytest.mark.asyncio
    async def test_call_service_success(self, toolkit):
        toolkit.arguments.control_mode = PermissionModeEnum.ALLOW
        await toolkit.call_service(
            domain="light", service="turn_on", entity_id="light.living_room"
        )

    @pytest.mark.asyncio
    async def test_call_service_denied(self, toolkit):
        toolkit.arguments.control_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.call_service(domain="light", service="turn_on")

    @pytest.mark.asyncio
    async def test_send_notification_success(self, toolkit):
        toolkit.arguments.control_mode = PermissionModeEnum.ALLOW
        await toolkit.call_service(
            domain="notify", service="mobile_app", service_data={"message": "hello"}
        )

    @pytest.mark.asyncio
    async def test_get_services_success(self, toolkit, mock_ha_client):
        service_mock = MagicMock()
        service_mock.domain = MagicMock()
        service_mock.domain.domain_id = "light"
        service_mock.service_id = "turn_on"
        service_mock.name = "turn_on"
        service_mock.description = "Turn on"
        service_mock.fields = {}
        service_mock.target = None
        service_mock.response = None
        domain_mock = MagicMock()
        domain_mock.services = {"turn_on": service_mock}
        mock_ha_client.async_get_domains = AsyncMock(
            return_value={"light": domain_mock}
        )
        result = await toolkit.get_services()
        assert len(result) == 1
        assert result[0].name == "turn_on"

    @pytest.mark.asyncio
    async def test_get_entity_success(self, toolkit, mock_ha_client):
        result = await toolkit.get_entity("light.living_room")
        assert result.entity_id == "light.living_room"

    @pytest.mark.asyncio
    async def test_search_entities_success(self, toolkit, mock_ha_client):
        mock_ha_client.async_get_entities = AsyncMock(
            return_value={
                "light": MagicMock(
                    entities={
                        "light.living_room": MagicMock(
                            entity_id="light.living_room",
                            slug="living_room",
                            state=MagicMock(
                                entity_id="light.living_room",
                                state="on",
                                attributes={},
                                last_changed=None,
                                last_updated=None,
                                last_reported=None,
                                context=None,
                            ),
                        )
                    }
                )
            }
        )
        result = await toolkit.search_entities("living")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_entity_history_success(self, toolkit, mock_ha_client):
        from datetime import datetime, timezone

        async def _history_gen():
            ha_history = MagicMock()
            ha_history.states = []
            yield ha_history

        mock_ha_client.async_get_entity_histories = AsyncMock(
            return_value=_history_gen()
        )
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        result = await toolkit.get_entity_history("light.living_room", start, end)
        assert result.entity_id == "light.living_room"
