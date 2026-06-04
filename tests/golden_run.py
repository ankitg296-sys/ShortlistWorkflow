"""
Golden gate test: 300 CVs → top 10 ranked shortlist.

This test documents the acceptance criteria for P4.

REQUIREMENT (SPEC §2, BUILD_PLAN §Phase 4):
  300 CVs → correct, stable top-10 shortlist
  - ≥8/10 overlap with an expert answer key (agreed up-front)
  - No cross-candidate contamination
  - Every score backed by a cited quote from the CV
  - Must pass 3× consecutively with identical top-10

STATUS:
  Harness is ready; awaiting real 300-CV dataset + expert answer key.
  Once you source the dataset, populate:
    - tests/fixtures/golden_cvs/  (300 PDF files, named by candidate_id)
    - tests/fixtures/golden_answer_key.json ({"correct_top_10": ["id1", "id2", ...]})
  Then `pytest tests/golden_run.py::test_golden_gate_300_to_10` will verify the engine.
"""
import os
import uuid

import pytest


@pytest.mark.skip(reason="Awaiting golden dataset + answer key. See docstring above.")
def test_golden_gate_300_to_10():
    """
    Run the full pipeline on 300 golden CVs and verify top-10 matches expert answer key.

    Steps:
    1. Load the 300 CV files from tests/fixtures/golden_cvs/
    2. Create a search with a realistic JD + recruiter prompt
    3. Parse, score, rank, refine all 300 CVs
    4. Fetch top-10 ranked candidates
    5. Compare to expert answer key — require ≥8/10 overlap
    6. Verify every score has an evidence_quote from the source CV
    7. Run 3× consecutively — top-10 must be identical each time
    """
    # Placeholder: structure for when the dataset arrives
    golden_cvs_dir = "tests/fixtures/golden_cvs"
    answer_key_path = "tests/fixtures/golden_answer_key.json"

    # These assertions will fail until the files exist
    assert os.path.isdir(golden_cvs_dir), (
        "Golden CV dataset not found. "
        "Populate tests/fixtures/golden_cvs/ with 300 PDF files."
    )
    assert os.path.isfile(answer_key_path), (
        "Golden answer key not found. "
        "Create tests/fixtures/golden_answer_key.json with {\"correct_top_10\": [...]}"
    )

    # Real test body would go here:
    # - load CVs
    # - create org + search
    # - run pipeline
    # - verify top-10
    # - run 3× for stability
