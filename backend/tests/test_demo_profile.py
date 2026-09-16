"""Cross-router regression: new teacher demo seed leaves /profile readable."""


def test_demo_seed_profile_readable_for_new_teacher(client, db):
    reg = client.post(
        "/api/auth/register",
        json={"email": "newteacher@test.example", "password": "123456", "name": "新老师"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    before = client.get("/api/profile", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["stats"]["interactions"] == 0

    seeded = client.post("/api/data/demo/seed", headers=headers)
    assert seeded.status_code == 200, seeded.text

    after = client.get("/api/profile", headers=headers)
    assert after.status_code == 200, after.text
    body = after.json()
    assert len(body["classes"]) >= 2
    assert body["stats"]["interactions"] > 0
