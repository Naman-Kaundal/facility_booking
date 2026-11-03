"""Rate-category rules: IIT comes only from the verified email; externals pick GOVT or PRIVATE."""


async def test_external_user_chooses_govt(sign_in):
    me = await sign_in("officer@gov.in", category=None)
    response = await me.put("/api/v1/users/me/rate-category", json={"rate_category": "GOVT"})
    assert response.status_code == 200
    assert response.json()["rate_category"] == "GOVT"
    assert response.json()["needs_category"] is False
    assert (await me.get("/api/v1/users/me")).json()["rate_category"] == "GOVT"


async def test_external_user_can_switch_to_private(sign_in):
    me = await sign_in("events@company.com", category="GOVT")
    response = await me.put("/api/v1/users/me/rate-category", json={"rate_category": "PRIVATE"})
    assert response.json()["rate_category"] == "PRIVATE"


async def test_external_user_cannot_claim_iit_rate(sign_in):
    me = await sign_in("someone@gmail.com", category=None)
    response = await me.put("/api/v1/users/me/rate-category", json={"rate_category": "IIT"})
    assert response.status_code == 422
    assert (await me.get("/api/v1/users/me")).json()["rate_category"] is None


async def test_extra_fields_are_rejected(sign_in):
    me = await sign_in("someone@gmail.com", category=None)
    response = await me.put(
        "/api/v1/users/me/rate-category", json={"rate_category": "GOVT", "is_iit": True, "email": "x@iitrpr.ac.in"}
    )
    assert response.status_code == 422


async def test_iit_user_cannot_change_category(sign_in):
    me = await sign_in("asha@iitrpr.ac.in")
    response = await me.put("/api/v1/users/me/rate-category", json={"rate_category": "PRIVATE"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CATEGORY_LOCKED"
    assert (await me.get("/api/v1/users/me")).json()["rate_category"] == "IIT"
