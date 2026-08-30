import httpx
import pytest


@pytest.mark.asyncio
async def test_list_toolkits(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        "/toolkits",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_get_toolkit_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        "/toolkits/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
