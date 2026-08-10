from __future__ import annotations

from app.workers import agent as agent_worker


def test_provider_circuit_opens_after_bounded_transient_failures() -> None:
    provider = "openai-test-circuit"
    with agent_worker._circuit_lock:
        agent_worker._circuit_failures.pop(provider, None)
        agent_worker._circuit_open_until.pop(provider, None)
    assert agent_worker._circuit_is_open(provider) is False
    for _ in range(agent_worker._PROVIDER_CIRCUIT_FAILURE_THRESHOLD):
        agent_worker._note_transient_provider_failure(provider)
    assert agent_worker._circuit_is_open(provider) is True
    agent_worker._note_provider_success(provider)
    assert agent_worker._circuit_is_open(provider) is False


def test_deterministic_provider_never_trips_circuit() -> None:
    for _ in range(agent_worker._PROVIDER_CIRCUIT_FAILURE_THRESHOLD + 5):
        agent_worker._note_transient_provider_failure("deterministic")
    assert agent_worker._circuit_is_open("deterministic") is False
