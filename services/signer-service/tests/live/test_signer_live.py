import os

import httpx


async def test_signer_returns_fresh_headers_repeatedly() -> None:
    token = os.environ["HONGGUO_SIGNER_SERVICE_TOKEN"]
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:18001",
        timeout=30,
    ) as client:
        for index in range(20):
            response = await client.post(
                "/v1/sign",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "url": (
                        "https://api5-normal-sinfonlinea.fqnovel.com/"
                        f"test?_rticket={index}"
                    ),
                    "headers": {},
                },
            )
            response.raise_for_status()
            assert response.json()["headers"]
