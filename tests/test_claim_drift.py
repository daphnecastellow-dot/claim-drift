import tempfile
import unittest
from pathlib import Path

from claim_drift import (
    DriftError, add_drift, add_source, add_version, audit, load, new_project,
    render_markdown, render_mermaid, render_timeline, save,
)


class ClaimDriftTests(unittest.TestCase):
    def test_multiple_changes_can_share_one_transition(self):
        data = new_project("Drift")
        v1 = add_version(data, "The door was open.")
        v2 = add_version(data, "The locked door had been forced open.")
        t1 = add_drift(data, v1, v2, "addition", "door", "locked door", "Lock state appears.")
        t2 = add_drift(data, v1, v2, "causal-shift", "was open", "had been forced open", "Mechanism is introduced.")
        self.assertEqual(t1, t2)
        self.assertEqual(len(data["transitions"]), 1)
        self.assertEqual(len(data["transitions"][0]["changes"]), 2)

    def test_drift_types_describe_change_not_motive(self):
        data = new_project("Types")
        v1 = add_version(data, "It may have happened.")
        v2 = add_version(data, "It happened.")
        add_drift(data, v1, v2, "certainty-shift", "may have happened", "happened", "Qualifier disappears.")
        self.assertEqual(data["transitions"][0]["changes"][0]["type"], "certainty-shift")

    def test_self_transition_is_rejected(self):
        data = new_project("Bad")
        v1 = add_version(data, "One wording.")
        with self.assertRaises(DriftError):
            add_drift(data, v1, v1, "other", "one", "one", "No transition.")

    def test_audit_flags_reverse_dated_transition_and_missing_note(self):
        data = new_project("Audit")
        later = add_source(data, "Later", "later-retelling", "1980")
        earlier = add_source(data, "Earlier", "primary", "1904")
        v1 = add_version(data, "Later wording.", [later])
        v2 = add_version(data, "Earlier wording.", [earlier])
        add_drift(data, v1, v2, "semantic-substitution", "later", "earlier")
        findings = audit(data)
        self.assertTrue(any("later dated version" in item for item in findings))
        self.assertTrue(any("no classification note" in item for item in findings))

    def test_round_trip_and_renderers(self):
        data = new_project("Render")
        s1 = add_source(data, "Early report", "primary", "1904")
        s2 = add_source(data, "Later account", "later-retelling", "1978")
        v1 = add_version(data, "The door was open.", [s1])
        v2 = add_version(data, "The door was found open.", [s2])
        add_drift(data, v1, v2, "addition", "", "found", "Discovery framing appears.")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "drift.json"; save(p, data); loaded = load(p)
        self.assertIn("addition", render_markdown(loaded))
        self.assertIn("V001", render_timeline(loaded))
        self.assertIn("addition", render_mermaid(loaded))


if __name__ == "__main__":
    unittest.main()
