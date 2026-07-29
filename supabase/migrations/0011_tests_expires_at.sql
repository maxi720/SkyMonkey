-- ===========================================================================
-- Tests: add expires_at column for optional test expiry.
--
-- After expires_at, the server refuses new attempt starts (checked in
-- test_take.py). NULL means no expiry. Existing tests are unaffected.
-- ===========================================================================

alter table public.tests
    add column if not exists expires_at timestamptz;
