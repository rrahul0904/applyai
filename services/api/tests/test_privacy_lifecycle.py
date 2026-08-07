def test_account_export_is_candidate_scoped_and_machine_readable(client):
    me = client.get("/api/v1/me")
    assert me.status_code == 200
    exported = client.get("/api/v1/account/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["user"]["email"] == me.json()["email"]
    assert body["user"]["account_status"] == "ACTIVE"
    assert isinstance(body["data"], dict)
