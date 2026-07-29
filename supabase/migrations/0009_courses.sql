-- ===========================================================================
-- Courses: bundle groups and uploaded materials under a single course.
--
-- A course belongs to a trainer (owner_id). Multiple groups can be assigned to
-- it; trainees in those groups can see the course and download its files.
-- Files are stored as hex-encoded binary in course_files.data (suitable for
-- small attachments; large-file hosting via Supabase Storage is a future step).
--
-- RLS design:
--   * A trainer owns their courses and can do everything.
--   * A trainee can SELECT a course if they are an accepted member of at least
--     one group that is assigned to that course.
--   * course_groups and course_files inherit the same visibility rule.
--   * Only the owning trainer may INSERT / UPDATE / DELETE.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Tables
-- ---------------------------------------------------------------------------

create table if not exists public.courses (
    id          uuid        primary key default gen_random_uuid(),
    owner_id    uuid        not null references public.profiles (id) on delete cascade,
    name        text        not null,
    description text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists courses_owner_idx on public.courses (owner_id);

-- Which groups have access to a course.
create table if not exists public.course_groups (
    course_id   uuid not null references public.courses (id) on delete cascade,
    group_id    uuid not null references public.groups  (id) on delete cascade,
    primary key (course_id, group_id)
);

-- Files attached to a course.
create table if not exists public.course_files (
    id           uuid        primary key default gen_random_uuid(),
    course_id    uuid        not null references public.courses  (id) on delete cascade,
    owner_id     uuid        not null references public.profiles (id) on delete cascade,
    name         text        not null,
    filename     text,
    content_type text        not null default 'application/octet-stream',
    size         int         not null default 0,
    data         text,                        -- hex-encoded binary content
    created_at   timestamptz not null default now()
);

create index if not exists course_files_course_idx on public.course_files (course_id);

-- ---------------------------------------------------------------------------
-- 2. Enable RLS
-- ---------------------------------------------------------------------------

alter table public.courses       enable row level security;
alter table public.course_groups enable row level security;
alter table public.course_files  enable row level security;

-- ---------------------------------------------------------------------------
-- 3. Grant table-level privileges to the authenticated role
-- ---------------------------------------------------------------------------

grant select, insert, update, delete on public.courses       to authenticated;
grant select, insert, update, delete on public.course_groups to authenticated;
grant select, insert, update, delete on public.course_files  to authenticated;

-- ---------------------------------------------------------------------------
-- 4. RLS policies — courses
-- ---------------------------------------------------------------------------

drop policy if exists "trainer owns course"          on public.courses;
drop policy if exists "trainee reads assigned course" on public.courses;

-- Trainer: full access to own courses.
create policy "trainer owns course"
    on public.courses
    for all
    using  (owner_id = auth.uid())
    with check (owner_id = auth.uid());

-- Trainee: can SELECT courses they have access to through a group membership.
create policy "trainee reads assigned course"
    on public.courses
    for select
    using (
        exists (
            select 1
            from   public.course_groups cg
            join   public.group_members gm on gm.group_id = cg.group_id
            where  cg.course_id = courses.id
              and  gm.user_id   = auth.uid()
              and  gm.status    = 'accepted'
        )
    );

-- ---------------------------------------------------------------------------
-- 5. RLS policies — course_groups
-- ---------------------------------------------------------------------------

drop policy if exists "trainer manages course groups" on public.course_groups;
drop policy if exists "trainee reads course groups"   on public.course_groups;

-- Trainer: manage group assignments on own courses.
create policy "trainer manages course groups"
    on public.course_groups
    for all
    using (
        exists (
            select 1 from public.courses c
            where c.id = course_groups.course_id
              and c.owner_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from public.courses c
            where c.id = course_groups.course_id
              and c.owner_id = auth.uid()
        )
    );

-- Trainee: read course_groups for courses they can see.
create policy "trainee reads course groups"
    on public.course_groups
    for select
    using (
        exists (
            select 1
            from   public.group_members gm
            where  gm.group_id = course_groups.group_id
              and  gm.user_id  = auth.uid()
              and  gm.status   = 'accepted'
        )
    );

-- ---------------------------------------------------------------------------
-- 6. RLS policies — course_files
-- ---------------------------------------------------------------------------

drop policy if exists "trainer manages course files" on public.course_files;
drop policy if exists "trainee reads course files"   on public.course_files;

-- Trainer: full access to files on own courses.
create policy "trainer manages course files"
    on public.course_files
    for all
    using  (owner_id = auth.uid())
    with check (owner_id = auth.uid());

-- Trainee: read files on courses they are assigned to.
create policy "trainee reads course files"
    on public.course_files
    for select
    using (
        exists (
            select 1
            from   public.course_groups cg
            join   public.group_members gm on gm.group_id = cg.group_id
            where  cg.course_id = course_files.course_id
              and  gm.user_id   = auth.uid()
              and  gm.status    = 'accepted'
        )
    );

-- ---------------------------------------------------------------------------
-- 7. updated_at trigger (same pattern as quizzes / tests)
-- ---------------------------------------------------------------------------

create or replace function public.set_course_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

drop trigger if exists courses_updated_at on public.courses;
create trigger courses_updated_at
    before update on public.courses
    for each row execute procedure public.set_course_updated_at();
