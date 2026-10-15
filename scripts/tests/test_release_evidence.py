import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("release_evidence", Path(__file__).resolve().parents[1] / "verify_release_evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SHA = "a" * 40
STAMP = "2026-10-01T17:00:00Z"


def proof(**extra):
    return dict(result="PASS", repository_sha=SHA, verified_at=STAMP, evidence="artifacts/check.log", **extra)


def ledger(state="REPOSITORY_VERIFIED"):
    return {
        "release_candidate_sha": SHA,
        "capabilities": [dict(
            capability="Radar", agent="Job Radar", status=state, repository_sha=SHA,
            branch="codex/release", pr="", issue="", tests=[proof()], workflow_runs=[],
            runtime_evidence=[], known_gaps=[], next_action="Stage", verified_at=STAMP,
        )],
        "gates": {name: proof() for name in module.GATES["production"]},
        "deployments": {name: proof(environment="production") for name in ("web", "api", "worker")},
        "release_issues": [],
    }


class ReleaseEvidenceTests(unittest.TestCase):
    def test_repository_claim_requires_matching_test_sha(self):
        data = ledger()
        self.assertEqual([], module.validate(data, target="repository"))
        data["capabilities"][0]["tests"][0]["repository_sha"] = "b" * 40
        self.assertTrue(module.validate(data))

    def test_repository_tests_do_not_prove_staging(self):
        self.assertTrue(module.validate(ledger("STAGING_VERIFIED")))

    def test_staging_proof_does_not_prove_production(self):
        data = ledger("PRODUCTION_DEPLOYED")
        data["capabilities"][0]["runtime_evidence"] = [proof(environment="staging")]
        self.assertTrue(module.validate(data))

    def test_blocked_is_valid_but_cannot_open_gates(self):
        data = ledger("BLOCKED")
        data["capabilities"][0]["known_gaps"] = ["No operator"]
        data["gates"]["auth"]["result"] = "BLOCKED"
        self.assertEqual([], module.validate(data))
        self.assertTrue(module.validate(data, target="production"))

    def test_automated_uat_cannot_satisfy_human_gate(self):
        data = ledger()
        data["gates"]["human_uat"]["sessions"] = [proof(human=False, participant_id=str(i)) for i in range(5)]
        self.assertTrue(module.validate(data, target="production"))

    def test_five_distinct_human_sessions_and_aligned_deployments(self):
        data = ledger("PRODUCTION_CERTIFIED")
        data["capabilities"][0]["runtime_evidence"] = [proof(environment="staging"), proof(environment="production")]
        data["gates"]["human_uat"]["sessions"] = [proof(human=True, participant_id=str(i)) for i in range(5)]
        self.assertEqual([], module.validate(data))
        data["deployments"]["worker"]["repository_sha"] = "b" * 40
        self.assertTrue(module.validate(data))

    def test_repeated_participant_does_not_count_as_five(self):
        data = ledger()
        data["gates"]["human_uat"]["sessions"] = [proof(human=True, participant_id="same") for _ in range(5)]
        self.assertTrue(module.validate(data, target="production"))

    def test_unresolved_p1_blocks_production(self):
        data = ledger()
        data["release_issues"] = [dict(severity="P1", title="Auth", resolved=False)]
        self.assertTrue(any("unresolved P1" in e for e in module.validate(data, target="production")))

    def test_structural_validation(self):
        for mutation in (lambda d: d.update(release_candidate_sha="HEAD"), lambda d: d["capabilities"][0].update(status="mostly done"), lambda d: d["capabilities"][0].update(verified_at="2026-10-01")):
            data = copy.deepcopy(ledger())
            mutation(data)
            self.assertTrue(module.validate(data))

    def test_invalid_json_types_fail_without_crash(self):
        self.assertTrue(module.validate([]))
        data = ledger()
        data["capabilities"][0]["tests"] = None
        self.assertTrue(module.validate(data))
        data["gates"] = None
        self.assertTrue(module.validate(data, target="production"))


if __name__ == "__main__":
    unittest.main()
