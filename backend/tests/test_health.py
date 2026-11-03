async def test_health_ok_with_real_database(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "environment": "test"}


async def test_health_reports_unreachable_database(unhealthy_client):
    response = await unhealthy_client.get("/api/v1/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"


async def test_health_when_postgres_is_down(offline_client):
    response = await offline_client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"


async def test_endpoints_return_503_when_postgres_is_down(offline_client):
    response = await offline_client.get("/api/v1/facilities")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


async def test_unknown_route_uses_error_format(client):
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
