from app.ai.semantic_matching import cosine, local_embedding, rerank


def test_local_embedding_is_deterministic_and_normalized():
    first = local_embedding("Python Snowflake data platform leadership")
    second = local_embedding("Python Snowflake data platform leadership")
    assert first == second
    assert abs(cosine(first, first) - 1.0) < 1e-9


def test_local_semantic_reranker_prioritizes_overlap(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    results = rerank(
        "director data engineering snowflake platform",
        [
            ("relevant", "Director of Data Engineering leading a Snowflake data platform"),
            ("other", "Retail store associate customer service"),
        ],
    )
    assert results[0][0] == "relevant"
    assert results[0][1] > results[1][1]
