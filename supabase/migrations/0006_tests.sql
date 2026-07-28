-- ===========================================================================
-- Tests (formal assessments), on top of the existing quizzes.
--
-- A test is an exam built from one or more quizzes. Unlike a quiz it:
--   * freezes its questions (a snapshot, so later quiz edits don't change it),
--   * gives no per-question feedback — only a final score,
--   * has a pass threshold, a limited number of attempts, and rules for how
--     random questions are drawn and re-drawn.
--
-- INTEGRITY: the correct answers must never reach the trainee's client. So the
-- answer key (test_questions.correct, test_pool.correct, test_attempts.*) is
-- NOT selectable by trainees under RLS. Drawing questions and scoring happen
-- server-side (the web app, with a server-only key); the trainee only ever
-- receives sanitised questions and, at the end, the score. Trainees read the
-- `tests` row (name, pass %, attempts) and their share, nothing sensitive.
-- ===========================================================================

-- --- tables -----------------------------------------------------------------
create table if not exists public.tests (
    id             uuid primary key default gen_random_uuid(),
    owner_id       uuid not null references public.profiles (id) on delete cascade,
    name           text not null,
    pass_percent   int  not null default 60 check (pass_percent between 0 and 100),
    max_attempts   int  not null default 1  check (max_attempts >= 1),
    -- 'manual' = hand-picked questions; 'random' = drawn from weighted sources.
    selection_mode text not null default 'random'
                        check (selection_mode in ('manual', 'random')),
    question_count int  not null default 0  check (question_count >= 0),
    -- On a retry: same questions again, or a fresh random draw.
    retry_mode     text not null default 'new'
                        check (retry_mode in ('same', 'new')),
    -- Who gets which random questions: a per-trainee draw, or one fixed set
    -- shared by everyone.
    draw_scope     text not null default 'per_trainee'
                        check (draw_scope in ('per_trainee', 'fixed')),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

-- Weighted sources for random tests: which quiz, what share, how many questions
-- that share works out to (computed once, at creation).
create table if not exists public.test_sources (
    id             uuid primary key default gen_random_uuid(),
    test_id        uuid not null references public.tests (id) on delete cascade,
    quiz_id        uuid not null references public.quizzes (id) on delete cascade,
    weight_percent int  not null check (weight_percent between 0 and 100),
    target_count   int  not null default 0 check (target_count >= 0),
    source_no      int  not null default 0
);

-- The fixed question set: manual picks, or a 'fixed' random draw frozen at
-- creation. Everyone taking the test sees exactly these.
create table if not exists public.test_questions (
    id        uuid primary key default gen_random_uuid(),
    test_id   uuid not null references public.tests (id) on delete cascade,
    position  int  not null default 0,
    prompt    text not null,
    options   jsonb not null,        -- array of answer strings
    correct   text not null          -- the correct answer (one of options)
);

-- Candidate pool for a per-trainee random draw: every eligible question from
-- each source, tagged with its source. The server draws target_count from each.
create table if not exists public.test_pool (
    id        uuid primary key default gen_random_uuid(),
    test_id   uuid not null references public.tests (id) on delete cascade,
    source_no int  not null default 0,
    prompt    text not null,
    options   jsonb not null,
    correct   text not null
);

create table if not exists public.test_shares (
    id        uuid primary key default gen_random_uuid(),
    test_id   uuid not null references public.tests (id) on delete cascade,
    group_id  uuid not null references public.groups (id) on delete cascade,
    shared_at timestamptz not null default now(),
    unique (test_id, group_id)
);

-- One row per attempt a trainee makes. `questions` is the snapshot actually
-- presented (with correct answers, for server-side scoring); `answers` is what
-- they submitted. Sensitive — trainees never select this table directly.
create table if not exists public.test_attempts (
    id            uuid primary key default gen_random_uuid(),
    test_id       uuid not null references public.tests (id) on delete cascade,
    user_id       uuid not null references public.profiles (id) on delete cascade,
    attempt_no    int  not null,
    status        text not null default 'in_progress'
                       check (status in ('in_progress', 'completed')),
    questions     jsonb not null,
    answers       jsonb,
    score_percent int,
    passed        boolean,
    started_at    timestamptz not null default now(),
    completed_at  timestamptz,
    unique (test_id, user_id, attempt_no)
);

create index if not exists test_sources_test_idx   on public.test_sources (test_id);
create index if not exists test_questions_test_idx on public.test_questions (test_id);
create index if not exists test_pool_test_idx      on public.test_pool (test_id);
create index if not exists test_shares_group_idx   on public.test_shares (group_id);
create index if not exists test_attempts_test_idx  on public.test_attempts (test_id);
create index if not exists test_attempts_user_idx  on public.test_attempts (user_id);

alter table public.tests          enable row level security;
alter table public.test_sources   enable row level security;
alter table public.test_questions enable row level security;
alter table public.test_pool      enable row level security;
alter table public.test_shares    enable row level security;
alter table public.test_attempts  enable row level security;

-- Keep updated_at current (reuses the trigger function from 0005).
drop trigger if exists tests_touch_updated_at on public.tests;
create trigger tests_touch_updated_at
    before update on public.tests
    for each row
    execute function public.touch_updated_at();

-- --- access helpers (SECURITY DEFINER, same pattern as 0001) ----------------
create or replace function public.is_test_owner(tid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1 from public.tests where id = tid and owner_id = auth.uid()
    );
$$;

create or replace function public.test_shared_with_me(tid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1
        from public.test_shares ts
        join public.group_members gm on gm.group_id = ts.group_id
        where ts.test_id = tid
          and gm.user_id = auth.uid()
          and gm.status = 'accepted'
    );
$$;

-- --- policies ---------------------------------------------------------------
-- tests: owner manages fully; trainees may read a test shared with them (only
-- non-sensitive columns live here — name, pass %, attempts).
drop policy if exists "tests: owner manages" on public.tests;
create policy "tests: owner manages"
    on public.tests for all
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

drop policy if exists "tests: shared read" on public.tests;
create policy "tests: shared read"
    on public.tests for select
    using (public.test_shared_with_me(public.tests.id));

-- sources / questions / pool: owner only. These hold the answer key, so there
-- is deliberately no trainee-facing policy — the server reads them with its own
-- key when drawing and scoring.
drop policy if exists "test_sources: owner" on public.test_sources;
create policy "test_sources: owner"
    on public.test_sources for all
    using (public.is_test_owner(public.test_sources.test_id))
    with check (public.is_test_owner(public.test_sources.test_id));

drop policy if exists "test_questions: owner" on public.test_questions;
create policy "test_questions: owner"
    on public.test_questions for all
    using (public.is_test_owner(public.test_questions.test_id))
    with check (public.is_test_owner(public.test_questions.test_id));

drop policy if exists "test_pool: owner" on public.test_pool;
create policy "test_pool: owner"
    on public.test_pool for all
    using (public.is_test_owner(public.test_pool.test_id))
    with check (public.is_test_owner(public.test_pool.test_id));

-- shares: owner manages; members may read (to discover a test is shared).
drop policy if exists "test_shares: owner manages" on public.test_shares;
create policy "test_shares: owner manages"
    on public.test_shares for all
    using (public.is_test_owner(public.test_shares.test_id))
    with check (public.is_test_owner(public.test_shares.test_id));

drop policy if exists "test_shares: members read" on public.test_shares;
create policy "test_shares: members read"
    on public.test_shares for select
    using (public.is_group_member(public.test_shares.group_id));

-- attempts: the test owner (trainer) may read them for the results view.
-- Trainees do not touch this table directly — the answer key is embedded in
-- `questions`. All writes and trainee-facing reads go through the server.
drop policy if exists "test_attempts: owner reads" on public.test_attempts;
create policy "test_attempts: owner reads"
    on public.test_attempts for select
    using (public.is_test_owner(public.test_attempts.test_id));

-- --- grants -----------------------------------------------------------------
grant select, insert, update, delete on public.tests          to authenticated;
grant select, insert, update, delete on public.test_sources   to authenticated;
grant select, insert, update, delete on public.test_questions to authenticated;
grant select, insert, update, delete on public.test_pool      to authenticated;
grant select, insert, update, delete on public.test_shares    to authenticated;
grant select                         on public.test_attempts  to authenticated;

grant execute on function public.is_test_owner(uuid)       to authenticated;
grant execute on function public.test_shared_with_me(uuid) to authenticated;
