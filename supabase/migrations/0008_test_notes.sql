-- Optional free-text notes a trainer can attach to a test (same idea as quiz
-- notes: trainer-only, e.g. what the test covers or which cohort it's for).
-- Nullable, so existing tests are unaffected. RLS already covers the tests
-- table, so no new policies are needed for another column.

alter table public.tests
    add column if not exists notes text;
