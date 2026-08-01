from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models import Company, Job


def seed_ranked_jobs(database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        strong_company = Company(
            canonical_name="Strong Match Labs",
            normalized_name="strong match labs",
        )
        weak_company = Company(
            canonical_name="Weak Match Labs",
            normalized_name="weak match labs",
        )
        session.add_all([strong_company, weak_company])
        session.flush()

        strong = Job(
            company_id=strong_company.id,
            title="Python Platform Engineer",
            normalized_title="python platform engineer",
            description=(
                "Python platform engineering with Python services, Python tooling, "
                "and Python production operations."
            ),
            search_document="",
            status="ACTIVE",
            data_origin="TEST",
        )
        weak = Job(
            company_id=weak_company.id,
            title="Data Operations Engineer",
            normalized_title="data operations engineer",
            description="Supports a platform that includes occasional Python maintenance.",
            search_document="",
            status="ACTIVE",
            data_origin="TEST",
        )
        session.add_all([strong, weak])
        session.flush()
        session.execute(
            text(
                "UPDATE jobs SET search_document = concat_ws(' ', title, description), "
                "search_vector = to_tsvector('english', concat_ws(' ', title, description)) "
                "WHERE id IN (:strong_id, :weak_id)"
            ),
            {"strong_id": strong.id, "weak_id": weak.id},
        )
        session.commit()
        strong_id = strong.id
        weak_id = weak.id
    engine.dispose()
    return strong_id, weak_id


def test_keyword_search_orders_by_lexical_rank_then_paginates_deterministically(
    client,
    database_url,
):
    strong_id, weak_id = seed_ranked_jobs(database_url)

    first = client.get("/api/v1/jobs", params={"keyword": "python", "limit": 1})
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["returned"] == 1
    assert first_payload["items"][0]["id"] == str(strong_id)
    assert first_payload["next_cursor"]

    second = client.get(
        "/api/v1/jobs",
        params={
            "keyword": "python",
            "limit": 1,
            "cursor": first_payload["next_cursor"],
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["returned"] == 1
    assert second_payload["items"][0]["id"] == str(weak_id)
    assert second_payload["items"][0]["id"] != first_payload["items"][0]["id"]
