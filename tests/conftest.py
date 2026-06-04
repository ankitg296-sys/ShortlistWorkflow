import os

# Set required env vars before any service module is imported.
# conftest.py runs before pytest collects and imports test files.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("ENCRYPTION_MASTER_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3Q=")
# Must match TEST_JWT_SECRET in test_auth.py — used to sign and verify test JWTs
os.environ.setdefault(
    "SUPABASE_JWT_SECRET", "test-jwt-secret-for-unit-tests-long-enough-for-hs256-alg!!"
)
# Must match TEST_INTERNAL_TOKEN in test_routing.py
os.environ.setdefault("INTERNAL_AUTH_TOKEN", "test-internal-token-for-routing-tests")
os.environ.setdefault("PROCESSING_SERVICE_URL", "http://localhost:8002")
# intake-service now also needs service role key (for Storage uploads)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
