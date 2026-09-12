"""Endpoint happy-path and common-failure tests."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_programs_seeded(client):
    resp = client.get("/programs")
    assert resp.status_code == 200
    programs = resp.json()
    assert len(programs) >= 8
    codes = {p["code"] for p in programs}
    assert "BISP_KAFAALAT" in codes


def test_create_and_get_case_with_situation(client):
    payload = {
        "raw_text": "My father lost his daily-wage job. We are six people.",
        "language": "en",
        "situation": {
            "household_size": 6,
            "monthly_income": 20000,
            "province": "Punjab",
            "employment_status": "unemployed",
            "facts": {"pmt_score": 18, "has_cnic": True, "gender": "female"},
        },
    }
    resp = client.post("/cases", json=payload)
    assert resp.status_code == 201
    case = resp.json()
    case_id = case["id"]
    assert case["situation"]["household_size"] == 6

    got = client.get(f"/cases/{case_id}")
    assert got.status_code == 200
    assert got.json()["id"] == case_id


def test_get_missing_case_returns_error_envelope(client):
    resp = client.get("/cases/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert "message" in body["error"]


def test_full_match_flow(client):
    # Create a case whose facts qualify for BISP Kafaalat.
    payload = {
        "raw_text": "Low-income woman, registered, needs cash support.",
        "situation": {
            "facts": {
                "pmt_score": 18,
                "has_cnic": True,
                "gender": "female",
                "province": "Punjab",
                "monthly_income": 20000,
                "children_in_school": 2,
                "has_pregnant_member": True,
            }
        },
    }
    case_id = client.post("/cases", json=payload).json()["id"]

    run = client.post(f"/cases/{case_id}/match")
    assert run.status_code == 200
    body = run.json()
    assert body["count"] >= 8
    # Results are sorted best-first.
    top = body["matches"][0]
    assert top["match_level"] in {"eligible", "likely"}

    listed = client.get(f"/cases/{case_id}/matches")
    assert listed.status_code == 200
    assert len(listed.json()) == body["count"]

    # Find the Kafaalat program result and confirm it is eligible.
    programs = {p["id"]: p for p in client.get("/programs").json()}
    kafaalat_id = next(
        pid for pid, p in programs.items() if p["code"] == "BISP_KAFAALAT"
    )
    kafaalat_match = next(
        m for m in listed.json() if m["program_id"] == kafaalat_id
    )
    assert kafaalat_match["match_level"] == "eligible"


def test_update_situation_changes_matches(client):
    case_id = client.post("/cases", json={"raw_text": "test"}).json()["id"]

    # No facts yet -> Kafaalat needs info.
    client.post(f"/cases/{case_id}/match")

    # Provide disqualifying facts.
    client.put(
        f"/cases/{case_id}/situation",
        json={"facts": {"pmt_score": 90, "has_cnic": True, "gender": "female"}},
    )
    rerun = client.post(f"/cases/{case_id}/match").json()
    programs = {p["id"]: p for p in client.get("/programs").json()}
    kafaalat_id = next(
        pid for pid, p in programs.items() if p["code"] == "BISP_KAFAALAT"
    )
    kafaalat = next(m for m in rerun["matches"] if m["program_id"] == kafaalat_id)
    assert kafaalat["match_level"] == "not_eligible"


def test_task_create_and_status_update(client):
    case_id = client.post("/cases", json={"raw_text": "test"}).json()["id"]

    created = client.post(
        f"/cases/{case_id}/tasks",
        json={"title": "Collect CNIC copy", "priority": "high"},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "pending"
    assert task["priority"] == "high"

    updated = client.patch(f"/tasks/{task['id']}", json={"status": "completed"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    tasks = client.get(f"/cases/{case_id}/tasks").json()
    assert len(tasks) == 1


def test_document_persistence(client):
    case_id = client.post("/cases", json={"raw_text": "test"}).json()["id"]
    resp = client.post(
        f"/cases/{case_id}/documents",
        json={
            "doc_type": "cnic",
            "filename": "cnic.jpg",
            "status": "processed",
            "extracted_fields": {"name": "Ayesha", "cnic": "35202-XXXXXXX-2"},
            "confidence": 0.92,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["extracted_fields"]["name"] == "Ayesha"

    docs = client.get(f"/cases/{case_id}/documents").json()
    assert len(docs) == 1


def test_validation_error_envelope(client):
    # household_size must be >= 0; -1 triggers a 422 with the shared envelope.
    resp = client.post(
        "/cases", json={"situation": {"household_size": -1}}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
