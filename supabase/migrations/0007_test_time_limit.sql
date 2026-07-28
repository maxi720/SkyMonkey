-- Optional time limit for a test. NULL = no limit (the default). When set, the
-- trainee sees a countdown while taking the test; the server is the authority
-- (it stores started_at and rejects/auto-scores a submission that arrives after
-- started_at + time_limit), so the countdown cannot be cheated by stopping the
-- client clock.

alter table public.tests
    add column if not exists time_limit_seconds int
        check (time_limit_seconds is null or time_limit_seconds > 0);
