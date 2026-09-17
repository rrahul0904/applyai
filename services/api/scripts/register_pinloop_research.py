from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.reverse_engineering import CLASSIFIER_VERSION
from app.reverse_engineering_models import ReverseEngineeringTopic

SOURCE_URL = "https://www.reddit.com/r/AgentsOfAI/s/TMzCnSDrbt"
PROJECT_URL = "https://github.com/pinloop/pinloop"


def upsert_pinloop_research(session: Session) -> ReverseEngineeringTopic:
    topic = session.scalar(
        select(ReverseEngineeringTopic).where(
            ReverseEngineeringTopic.source_url == SOURCE_URL
        )
    )
    values = {
        "title": "Pinloop agent-first job-search loop",
        "source_type": "PUBLIC_RESEARCH",
        "summary": (
            "Agent-first job-search workflow that continuously discovers fresh roles, "
            "judges them against a candidate profile, preserves reasoning, and reduces "
            "the search surface to a high-signal queue."
        ),
        "applyai_fit": "CORE",
        "fit_scope": "PARTIAL",
        "destination": "candidate-core",
        "rationale": (
            "ApplyAI already owns job supply, semantic matching, Career V2 scoring, and "
            "career-memory evidence. Absorb Pinloop's autonomous batch-judgment and "
            "high-signal queue pattern without duplicating its CLI or hosted backend."
        ),
        "classifier_version": CLASSIFIER_VERSION,
        "classification_source": "MANUAL",
        "candidate_journey_stages": [
            "DISCOVER_JOBS",
            "UNDERSTAND_FIT",
            "CAREER_INTELLIGENCE",
        ],
        "qualifying_capabilities": [
            "continuous fresh-job radar",
            "batch job judging against verified candidate evidence",
            "persistent explainable fit decisions",
            "high-signal shortlist prioritization",
            "refresh loop that evaluates only previously unjudged roles",
        ],
        "excluded_capabilities": [
            "standalone CLI shell",
            "Pinloop hosted backend",
            "third-party job-data dependency when ApplyAI supply already covers the role",
        ],
        "evidence_urls": [SOURCE_URL, PROJECT_URL],
        "status": "IMPLEMENTING",
        "implementation_target": (
            "services/api/app/api/career_radar.py + "
            "apps/web/components/recommended-jobs-view.tsx"
        ),
        "metadata_json": {
            "reference_product": "Pinloop",
            "integration_name": "ApplyAI Job Radar",
            "license_note": "Public CLI is used as an architectural reference; hosted service is not copied.",
        },
    }

    if topic is None:
        topic = ReverseEngineeringTopic(source_url=SOURCE_URL, **values)
        session.add(topic)
    else:
        for field, value in values.items():
            setattr(topic, field, value)

    session.commit()
    session.refresh(topic)
    return topic


def main() -> None:
    with SessionLocal() as session:
        topic = upsert_pinloop_research(session)
        print(f"registered {topic.id} {topic.title} [{topic.status}]")


if __name__ == "__main__":
    main()
