from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import (
    Application,
    Company,
    Job,
    JobCompensation,
    JobLocation,
    SavedJob,
    User,
)


@contextmanager
def sql_statement_counter():
    statements = {"count": 0}

    def before_cursor_execute(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        del connection, cursor, statement, parameters, context, executemany
        statements["count"] += 1

    event.listen(Engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", before_cursor_execute)


def seed_list_volume(client, database_url: str, count: int = 12) -> None:
    # Materialize the owner through the same auth boundary used by list requests.
    me = client.get("/api/v1/me")
    assert me.status_code == 200

    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.clerk_user_id == "clerk_user_a"))
        assert user is not None
        company = Company(
            canonical_name="Query Scale Labs",
            normalized_name="query scale labs",
            website_url="https://query-scale.example.test",
        )
        session.add(company)
        session.flush()

        now = datetime.now(timezone.utc)
        for index in range(count):
            job = Job(
                company_id=company.id,
                title=f"Data Engineer {index}",
                normalized_title=f"data engineer {index}",
                description="Production data engineering role used for query scaling tests.",
                search_document=f"Data Engineer {index} Query Scale Labs production data engineering",
                employment_type="FULL_TIME",
                seniority="SENIOR",
                status="ACTIVE",
                posted_at=now - timedelta(minutes=index),
            )
            session.add(job)
            session.flush()
            session.add_all(
                [
                    JobLocation(
                        job_id=job.id,
                        location_text="Boston, MA",
                        city="Boston",
                        region="MA",
                        country_code="US",
                        work_mode="HYBRID",
                    ),
                    JobCompensation(
                        job_id=job.id,
                        minimum=150000,
                        maximum=190000,
                        provenance="EMPLOYER_DISCLOSED",
                    ),
                    SavedJob(user_id=user.id, job_id=job.id),
                    Application(user_id=user.id, job_id=job.id, current_status="PREPARING"),
                ]
            )
        session.commit()
    engine.dispose()


def request_query_count(client, path: str, limit: int) -> tuple[int, dict]:
    with sql_statement_counter() as counter:
        response = client.get(path, params={"limit": limit})
    assert response.status_code == 200
    return counter["count"], response.json()


def test_job_list_query_count_does_not_scale_with_page_size(client, database_url):
    seed_list_volume(client, database_url)

    one_count, one_page = request_query_count(client, "/api/v1/jobs", 1)
    many_count, many_page = request_query_count(client, "/api/v1/jobs", 12)

    assert one_page["returned"] == 1
    assert many_page["returned"] == 12
    assert many_count == one_count


def test_saved_job_list_query_count_does_not_scale_with_page_size(client, database_url):
    seed_list_volume(client, database_url)

    one_count, one_page = request_query_count(client, "/api/v1/jobs/saved", 1)
    many_count, many_page = request_query_count(client, "/api/v1/jobs/saved", 12)

    assert one_page["returned"] == 1
    assert many_page["returned"] == 12
    assert many_count == one_count


def test_application_list_query_count_does_not_scale_with_page_size(client, database_url):
    seed_list_volume(client, database_url)

    one_count, one_page = request_query_count(client, "/api/v1/applications", 1)
    many_count, many_page = request_query_count(client, "/api/v1/applications", 12)

    assert one_page["returned"] == 1
    assert many_page["returned"] == 12
    assert many_count == one_count
