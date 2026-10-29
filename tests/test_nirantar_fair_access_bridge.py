"""The deployed Nirantar frontend needs a real JSON fair-access endpoint."""

from starlette.testclient import TestClient

from backend.app import app


def test_nirantar_fair_access_json_and_cross_origin() -> None:
    with TestClient(app) as client:
        preflight = client.options(
            "/api/v1/fair-access/admit",
            headers={
                "Origin": "https://bronze-tinsel-n8pb.here.now",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "https://bronze-tinsel-n8pb.here.now"

        admit = client.post(
            "/api/v1/fair-access/admit",
            json={"action": "SEARCH_TRAINS", "session_id": "test-bridge"},
        )
        assert admit.status_code == 200
        ticket = admit.json()
        assert ticket["ticketId"].startswith("FAQ-")
        assert ticket["status"] in {"ADMITTED", "QUEUED"}
        assert "prototype" in ticket["disclaimer"].lower()

        status = client.get(f"/api/v1/fair-access/status/{ticket['ticketId']}")
        assert status.status_code == 200
        assert status.json()["ticketId"] == ticket["ticketId"]
