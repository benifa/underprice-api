from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_score_paste_path(client: TestClient) -> None:
    r = client.post(
        "/v1/score",
        json={
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "description": "Noise cancelling over-ear",
            "ask": 198.0,
            "category": "headphones",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["job_id"]
    result = body["result"]
    assert result["ask"] == 198.0
    assert "median" in result["stages_run"]
    assert result["fair_value"] is not None


def test_score_job_poll(client: TestClient) -> None:
    created = client.post(
        "/v1/score",
        json={"title": "USB-C hub", "ask": 25.0, "category": "electronics"},
    ).json()
    job_id = created["job_id"]
    polled = client.get(f"/v1/score/{job_id}")
    assert polled.status_code == 200
    assert polled.json()["result"]["candidate_id"] == created["result"]["candidate_id"]


def test_deals_feed_never_scores(client: TestClient) -> None:
    # Force a hot deal into the store via a very low ask vs heuristic/median
    client.post(
        "/v1/score",
        json={
            "title": "Bargain headphones deal",
            "description": "MSRP $199 headphones",
            "ask": 40.0,
            "category": "headphones",
        },
    )
    feed = client.get("/v1/deals")
    assert feed.status_code == 200
    assert "items" in feed.json()


def test_prefs_and_devices(client: TestClient) -> None:
    resp = client.post("/v1/devices", json={"install_id": "i1", "fcm_token": "t"})
    assert resp.status_code == 204
    r = client.put(
        "/v1/prefs",
        json={"install_id": "i1", "keywords": ["sony"], "min_score": 0.7, "notify_enabled": True},
    )
    assert r.status_code == 200
    assert r.json()["keywords"] == ["sony"]
