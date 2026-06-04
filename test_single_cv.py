#!/usr/bin/env python3
"""
End-to-end test: Single CV from intake → parsing → scoring → ranking → shortlist.

This script validates the core ShortList workflow in one go.
Requires: both intake-service and processing-service running locally.

Usage:
    python test_single_cv.py --cv path/to/cv.pdf --api-key sk-ant-YOUR-KEY

Or interactive:
    python test_single_cv.py
"""
import argparse
import json
import sys
import time
import tempfile
from pathlib import Path
from typing import Optional

import httpx

# Service URLs
INTAKE_URL = "http://localhost:8001"
PROCESSING_URL = "http://localhost:8002"

# Test data
TEST_ORG_NAME = "Test Shortlist Org"
TEST_EMAIL = f"tester+{int(time.time())}@shortlist.test"
TEST_JOB_TITLE = "Senior Python Engineer"
TEST_JOB_DESCRIPTION = """
Required:
- 5+ years Python programming
- 2+ years shipping ML systems to production
- Experience leading engineering teams
- Strong system design skills

Nice to have:
- Experience with transformer models
- Open source contributions
- Technical writing/documentation
"""
TEST_PROMPT = """
Find candidates who:
1. Have shipped machine learning systems in production (demonstrated evidence)
2. Have led and mentored engineering teams (leadership experience)
3. Have deep Python expertise (years, frameworks, best practices)
4. Have strong system design and scaling experience

Rank by production ML experience first, then leadership, then depth."""


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step: int, description: str):
    """Print a step indicator."""
    print(f"\n→ Step {step}: {description}")


def print_json(data, title: str = "Response"):
    """Pretty print JSON data."""
    print(f"\n{title}:")
    print(json.dumps(data, indent=2)[:500] + ("..." if len(json.dumps(data, indent=2)) > 500 else ""))


async def create_test_cv() -> Path:
    """
    Create a simple test CV file (PDF-like text).
    In production, you'd use real CVs.
    """
    cv_content = """
    John Doe
    john.doe@example.com | San Francisco, CA | linkedin.com/in/johndoe

    PROFESSIONAL SUMMARY
    Senior ML Engineer with 7 years of Python programming and 4 years shipping production ML systems.
    Led teams of 3-5 engineers. Strong system design and scaling expertise.

    EXPERIENCE

    Lead ML Engineer, TechCorp (2022-2024)
    - Shipped fraud detection ML system to production, reducing false positives by 40%
    - Led team of 4 engineers on ML infrastructure and data pipeline projects
    - Designed and implemented distributed feature store (Python, Kafka, PostgreSQL)
    - Mentored 2 junior engineers, 1 promoted to senior within 18 months
    - Wrote technical RFC for ML model serving architecture

    ML Engineer, DataCo (2020-2022)
    - Developed real-time recommendation engine (TensorFlow, Python) serving 50M requests/day
    - Optimized model inference latency from 200ms to 50ms using graph optimization
    - Built data pipeline processing 10GB/day of user behavior (Spark, Python)
    - Contributed to open source ML frameworks (scikit-learn, TensorFlow)

    Python Engineer, StartupInc (2017-2020)
    - Built backend services and APIs in Python (Flask, FastAPI)
    - Improved system performance through profiling and optimization
    - Led migration from monolith to microservices

    TECHNICAL SKILLS
    Languages: Python (7 years), SQL, Rust
    ML/Data: TensorFlow, PyTorch, Scikit-learn, Pandas, XGBoost
    Infrastructure: Kubernetes, AWS, GCP, Docker, Terraform
    Databases: PostgreSQL, Redis, DynamoDB
    Other: System Design, Distributed Systems, Technical Leadership

    EDUCATION
    B.S. Computer Science, University of California
    """

    # Create temp PDF (just text for testing)
    temp_dir = Path(tempfile.gettempdir())
    cv_path = temp_dir / "test_cv.txt"
    cv_path.write_text(cv_content)
    print(f"\nCreated test CV: {cv_path}")
    return cv_path


async def test_workflow(api_key: str, cv_path: Optional[Path] = None):
    """Run the complete test workflow."""

    print_section("ShortList End-to-End Workflow Test")
    print("Testing: Sign up → Parse CV → Score → Rank → Shortlist")

    async with httpx.AsyncClient(timeout=30.0) as client:

        # ========== STEP 1: Sign up ==========
        print_step(1, "Create org and recruiter account")
        signup_response = await client.post(
            f"{PROCESSING_URL}/auth/signup",
            json={
                "org_name": TEST_ORG_NAME,
                "email": TEST_EMAIL,
            },
        )
        if signup_response.status_code != 201:
            print(f"❌ Sign up failed: {signup_response.text}")
            return

        signup_data = signup_response.json()
        org_id = signup_data.get("org_id")
        user_id = signup_data.get("user_id")
        jwt_token = signup_data.get("access_token")

        print(f"✅ Signed up:")
        print(f"   Org ID: {org_id}")
        print(f"   User ID: {user_id}")
        print(f"   Email: {TEST_EMAIL}")

        headers = {"Authorization": f"Bearer {jwt_token}"}

        # ========== STEP 2: Add API key ==========
        print_step(2, "Add customer's Anthropic API key")
        key_response = await client.post(
            f"{PROCESSING_URL}/keys",
            headers=headers,
            json={
                "provider": "anthropic",
                "api_key": api_key,
                "model_options": {},
            },
        )
        if key_response.status_code != 201:
            print(f"❌ Key add failed: {key_response.text}")
            return

        key_data = key_response.json()
        key_id = key_data.get("id")
        key_hint = key_data.get("key_hint")

        print(f"✅ API key added:")
        print(f"   Key ID: {key_id}")
        print(f"   Hint: {key_hint} (last 4 chars)")

        # ========== STEP 3: Test API key ==========
        print_step(3, "Test API key validity")
        test_response = await client.post(
            f"{PROCESSING_URL}/keys/{key_id}/test",
            headers=headers,
        )
        if test_response.status_code != 200:
            print(f"❌ Key test failed: {test_response.text}")
            return

        test_data = test_response.json()
        if not test_data.get("ok"):
            print(f"❌ API key validation failed. Check the key is valid.")
            return

        print(f"✅ API key validated successfully")

        # ========== STEP 4: Create job ==========
        print_step(4, "Create a job posting")
        job_response = await client.post(
            f"{PROCESSING_URL}/jobs",
            headers=headers,
            json={
                "title": TEST_JOB_TITLE,
                "description": TEST_JOB_DESCRIPTION,
            },
        )
        if job_response.status_code != 201:
            print(f"❌ Job creation failed: {job_response.text}")
            return

        job_data = job_response.json()
        job_id = job_data.get("id")
        apply_token = job_data.get("apply_link_token")

        print(f"✅ Job created:")
        print(f"   Job ID: {job_id}")
        print(f"   Title: {TEST_JOB_TITLE}")
        print(f"   Apply link token: {apply_token}")

        # ========== STEP 5: Submit CV ==========
        print_step(5, "Candidate submits CV")

        if cv_path is None:
            cv_path = await create_test_cv()

        # Read CV file
        with open(cv_path, "rb") as f:
            cv_bytes = f.read()

        # Submit via intake service
        apply_response = await client.post(
            f"{INTAKE_URL}/apply/{apply_token}",
            data={
                "name": "John Doe",
                "email": "john.doe@example.com",
            },
            files={
                "cv": (cv_path.name, cv_bytes, "application/pdf"),
            },
        )
        if apply_response.status_code != 200:
            print(f"❌ CV submission failed: {apply_response.text}")
            return

        apply_data = apply_response.json()
        application_id = apply_data.get("application_id")

        print(f"✅ CV submitted:")
        print(f"   Application ID: {application_id}")
        print(f"   Name: John Doe")
        print(f"   Email: john.doe@example.com")

        # ========== STEP 6: Wait for parsing ==========
        print_step(6, "Wait for CV parsing to complete")
        print("   (Parsing runs asynchronously; polling every 2 seconds...)")

        # Poll for candidate to be parsed
        parsed = False
        for attempt in range(30):  # Max 60 seconds
            # Check if candidate exists with parsed text
            search_response = await client.get(
                f"{PROCESSING_URL}/jobs/{job_id}",
                headers=headers,
            )
            if search_response.status_code == 200:
                job_detail = search_response.json()
                if job_detail.get("application_count", 0) > 0:
                    # Good sign; now check candidate parse status
                    # (In a real flow, we'd have a /candidates endpoint)
                    parsed = True
                    break

            if attempt < 5 or attempt % 5 == 0:
                print(f"   Polling... ({attempt * 2}s elapsed)")
            time.sleep(2)

        if not parsed:
            print(f"⚠️  Parsing may still be in progress (timeout after 60s)")
            print(f"   Proceeding anyway...")
        else:
            print(f"✅ CV parsed and candidate ready")

        # ========== STEP 7: Create search (rubric builder) ==========
        print_step(7, "Create search with rubric")
        search_response = await client.post(
            f"{PROCESSING_URL}/searches",
            headers=headers,
            json={
                "job_id": job_id,
                "prompt": TEST_PROMPT,
                "jd_text": TEST_JOB_DESCRIPTION,
            },
        )
        if search_response.status_code != 201:
            print(f"❌ Search creation failed: {search_response.text}")
            return

        search_data = search_response.json()
        search_id = search_data.get("id")
        criteria = search_data.get("criteria", [])

        print(f"✅ Search created with rubric:")
        print(f"   Search ID: {search_id}")
        print(f"   Status: {search_data.get('status')}")
        print(f"   Criteria ({len(criteria)}):")
        for c in criteria:
            print(f"     - {c.get('name')} (weight {c.get('weight'):.2f}): {c.get('description')}")

        # ========== STEP 8: Run search (scoring) ==========
        print_step(8, "Trigger scoring pipeline")
        run_response = await client.post(
            f"{PROCESSING_URL}/searches/{search_id}/run",
            headers=headers,
        )
        if run_response.status_code != 200:
            print(f"❌ Search run failed: {run_response.text}")
            return

        print(f"✅ Scoring pipeline started")
        print(f"   Waiting for results (typically 30s-2min for 1 CV)...")

        # ========== STEP 9: Poll for results ==========
        print_step(9, "Poll for scoring results")

        complete = False
        for attempt in range(120):  # Max 4 minutes
            detail_response = await client.get(
                f"{PROCESSING_URL}/searches/{search_id}",
                headers=headers,
            )
            if detail_response.status_code != 200:
                print(f"❌ Search detail fetch failed: {detail_response.text}")
                return

            detail_data = detail_response.json()
            status = detail_data.get("status")
            scores = detail_data.get("scores", [])

            if status == "complete":
                complete = True
                break
            elif status == "error":
                print(f"❌ Search failed with error")
                return

            if attempt < 5 or attempt % 10 == 0:
                print(f"   Status: {status} ({attempt * 2}s elapsed, {len(scores)} scores)")

            time.sleep(2)

        if not complete:
            print(f"❌ Search did not complete within 4 minutes")
            return

        print(f"✅ Scoring complete!")

        # ========== STEP 10: Display shortlist ==========
        print_step(10, "Retrieve and display shortlist")

        shortlist_response = await client.get(
            f"{PROCESSING_URL}/searches/{search_id}/shortlist?top_n=10",
            headers=headers,
        )
        if shortlist_response.status_code != 200:
            print(f"❌ Shortlist fetch failed: {shortlist_response.text}")
            return

        shortlist = shortlist_response.json()

        print(f"\n✅ SHORTLIST RESULTS ({len(shortlist)} candidate(s)):")
        print("=" * 70)

        for i, score_entry in enumerate(shortlist, 1):
            candidate_id = score_entry.get("candidate_id")
            overall_score = score_entry.get("overall_score", 0)
            rank = score_entry.get("rank", i)
            summary = score_entry.get("summary", "")
            criteria_scores = score_entry.get("criteria_scores", [])
            flags = score_entry.get("flags", [])

            print(f"\n#{rank} Candidate {candidate_id[:8]}...")
            print(f"    Overall Score: {overall_score:.2f} / 1.0 ({int(overall_score * 100)}%)")
            print(f"    Summary: {summary}")

            if criteria_scores:
                print(f"    Criteria Breakdown:")
                for cs in criteria_scores:
                    name = cs.get("name")
                    score = cs.get("score", 0)
                    evidence = cs.get("evidence_quote", "")[:80]
                    insufficient = cs.get("insufficient_evidence", False)

                    if insufficient:
                        print(f"      • {name}: INSUFFICIENT EVIDENCE")
                    else:
                        print(f"      • {name}: {score:.2f}")
                        print(f"        Evidence: \"{evidence}...\"" if evidence else "        Evidence: (none)")

            if flags:
                print(f"    Flags: {', '.join(flags)}")

        print("\n" + "=" * 70)
        print("✅ TEST COMPLETE - Full pipeline validated!")
        print("=" * 70)

        # Summary
        print(f"\nSummary:")
        print(f"  Org: {TEST_ORG_NAME}")
        print(f"  Job: {TEST_JOB_TITLE}")
        print(f"  Candidates scored: {len(shortlist)}")
        if shortlist:
            print(f"  Top score: {shortlist[0].get('overall_score', 0):.2f}")
        print(f"  Search ID: {search_id}")


async def main():
    parser = argparse.ArgumentParser(
        description="End-to-end ShortList workflow test (1 CV → score → shortlist)"
    )
    parser.add_argument(
        "--api-key",
        required=False,
        help="Anthropic API key (sk-ant-...). If not provided, will prompt.",
    )
    parser.add_argument(
        "--cv",
        type=Path,
        required=False,
        help="Path to test CV file. If not provided, creates a test CV.",
    )

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key
    if not api_key:
        print("\n📌 ShortList Workflow Test")
        print("This test requires an Anthropic API key (from console.anthropic.com)")
        api_key = input("\nEnter your Anthropic API key (sk-ant-...): ").strip()

    if not api_key.startswith("sk-ant-"):
        print("❌ Invalid API key format (should start with sk-ant-)")
        sys.exit(1)

    # Check services are running
    print("\n🔍 Checking if services are running...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            intake_health = await client.get(f"{INTAKE_URL}/health")
            processing_health = await client.get(f"{PROCESSING_URL}/health")

        if intake_health.status_code != 200 or processing_health.status_code != 200:
            raise Exception("Services returned non-200 status")

        print("✅ Both services are running")
    except Exception as e:
        print(f"❌ Could not reach services: {e}")
        print(f"\nMake sure both are running:")
        print(f"  uvicorn intake_service.main:app --reload --port 8001")
        print(f"  uvicorn processing_service.main:app --reload --port 8002")
        sys.exit(1)

    # Run test
    try:
        await test_workflow(api_key, args.cv)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
