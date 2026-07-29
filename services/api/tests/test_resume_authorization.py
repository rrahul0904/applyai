import io


def test_resume_upload_metadata_and_owner_isolation(client, switch_user):
    response = client.post(
        "/api/v1/resumes",
        files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 sample"), "application/pdf")},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "resume.pdf"
    assert payload["file_size"] == len(b"%PDF-1.4 sample")
    assert payload["upload_status"] == "UPLOADED"
    assert payload["processing_status"] == "QUEUED"
    assert "storage_key" not in payload
    assert len(client.storage.objects) == 1
    assert client.queue.tasks[0].task_type == "RESUME_PARSE"

    resume_id = payload["resume_id"]
    switch_user("clerk_user_b", "b@example.com")
    isolated = client.get(f"/api/v1/resumes/{resume_id}")
    assert isolated.status_code == 404


def test_resume_upload_rejects_mismatched_type(client):
    response = client.post(
        "/api/v1/resumes",
        files={"file": ("resume.pdf", io.BytesIO(b"not docx"), "text/plain")},
    )
    assert response.status_code == 400
