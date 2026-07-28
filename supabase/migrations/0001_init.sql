-- QuizMonkey schema: profiles, groups, memberships, shared quizzes.
--
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New
-- query -> paste -> Run). It is written to be re-runnable: every statement is
-- guarded, so applying it twice does no harm.
--
-- Structure: all tables are created first, then all policies. The policies
-- cross-reference each other's tables (a quiz is readable because of a row in
-- quiz_shares, which matters because of a row in group_members), and Postgres
-- resolves those names when the policy is created — so the tables have to
-- exist by then.
--
-- Design notes
--   * A profile row is created automatically for every new auth user by the
--     trigger at the bottom; first/last name and role come from the sign-up
--     metadata the app sends.
--   * "role" is the account's default view. A trainer may switch to the
--     trainee view in the UI; that is a client-side preference and is stored
--     in profiles.active_view so it survives a re-login.
--   * Row Level Security is on for every table. The policies are what actually
--     stops a trainee from reading other groups' quizzes, so they are not
--     optional.

-- ===========================================================================
-- 1. Tables
-- ===========================================================================

create table if not exists public.profiles (
    id          uuid primary key references auth.users (id) on delete cascade,
    email       text        not null,
    first_name  text        not null default '',
    last_name   text        not null default '',
    role        text        not null default 'trainee'
                  check (role in ('trainer', 'trainee')),
    active_view text        not null default 'trainee'
                  check (active_view in ('trainer', 'trainee')),
    created_at  timestamptz not null default now()
);

create table if not exists public.groups (
    id         uuid primary key default gen_random_uuid(),
    name       text        not null,
    owner_id   uuid        not null references public.profiles (id) on delete cascade,
    created_at timestamptz not null default now()
);

create index if not exists groups_owner_idx on public.groups (owner_id);

-- Membership and invitation in one table: an invitation is a row with status
-- 'invited'. Accepting flips it to 'accepted'. This keeps "is a member" and
-- "was invited" a single lookup and avoids a second table to keep in sync.
-- user_id stays null until the invited person actually has an account.
create table if not exists public.group_members (
    id          uuid primary key default gen_random_uuid(),
    group_id    uuid        not null references public.groups (id) on delete cascade,
    user_id     uuid        references public.profiles (id) on delete cascade,
    email       text        not null,
    status      text        not null default 'invited'
                  check (status in ('invited', 'accepted')),
    invited_at  timestamptz not null default now(),
    accepted_at timestamptz,
    unique (group_id, email)
);

create index if not exists group_members_user_idx on public.group_members (user_id);
create index if not exists group_members_email_idx on public.group_members (lower(email));

-- The CSV text is stored inline. Quizzes are small (a few KB), so a text
-- column avoids the extra round trip and the separate access rules that
-- Supabase Storage would bring.
create table if not exists public.quizzes (
    id         uuid primary key default gen_random_uuid(),
    owner_id   uuid        not null references public.profiles (id) on delete cascade,
    name       text        not null,
    csv        text        not null,
    created_at timestamptz not null default now()
);

create index if not exists quizzes_owner_idx on public.quizzes (owner_id);

create table if not exists public.quiz_shares (
    id        uuid primary key default gen_random_uuid(),
    quiz_id   uuid        not null references public.quizzes (id) on delete cascade,
    group_id  uuid        not null references public.groups (id) on delete cascade,
    shared_at timestamptz not null default now(),
    unique (quiz_id, group_id)
);

create index if not exists quiz_shares_group_idx on public.quiz_shares (group_id);

alter table public.profiles      enable row level security;
alter table public.groups        enable row level security;
alter table public.group_members enable row level security;
alter table public.quizzes       enable row level security;
alter table public.quiz_shares   enable row level security;

-- ===========================================================================
-- 2. Access helpers
--
-- These exist to break RLS recursion. A policy on `groups` that looks into
-- `group_members` triggers that table's policies, which look back into
-- `groups` — Postgres rejects the cycle with "infinite recursion detected".
--
-- SECURITY DEFINER makes the lookup run as the function owner, so the inner
-- query is not subject to RLS and the cycle never forms. Each function only
-- answers a yes/no question about the *calling* user, so it cannot be used to
-- read anyone else's data.
-- ===========================================================================

create or replace function public.is_group_owner(gid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1 from public.groups
        where id = gid and owner_id = auth.uid()
    );
$$;

create or replace function public.is_group_member(gid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1 from public.group_members
        where group_id = gid
          and user_id = auth.uid()
          and status = 'accepted'
    );
$$;

create or replace function public.shares_a_group_with(other_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1
        from public.group_members me
        join public.group_members them on them.group_id = me.group_id
        where me.user_id = auth.uid()
          and them.user_id = other_id
    );
$$;

create or replace function public.quiz_shared_with_me(qid uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1
        from public.quiz_shares qs
        join public.group_members gm on gm.group_id = qs.group_id
        where qs.quiz_id = qid
          and gm.user_id = auth.uid()
          and gm.status = 'accepted'
    );
$$;

-- ===========================================================================
-- 3. Policies
-- ===========================================================================

-- --- profiles ---------------------------------------------------------------
drop policy if exists "profiles: read own" on public.profiles;
create policy "profiles: read own"
    on public.profiles for select
    using (auth.uid() = id);

-- Members of a shared group need to see each other's names.
drop policy if exists "profiles: read fellow group members" on public.profiles;
create policy "profiles: read fellow group members"
    on public.profiles for select
    using (public.shares_a_group_with(public.profiles.id));

drop policy if exists "profiles: update own" on public.profiles;
create policy "profiles: update own"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id);

-- --- groups -----------------------------------------------------------------
drop policy if exists "groups: owner full access" on public.groups;
create policy "groups: owner full access"
    on public.groups for all
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

drop policy if exists "groups: members can read" on public.groups;
create policy "groups: members can read"
    on public.groups for select
    using (public.is_group_member(public.groups.id));

-- --- group_members ----------------------------------------------------------
-- The trainer who owns the group may invite and remove.
drop policy if exists "members: group owner manages" on public.group_members;
create policy "members: group owner manages"
    on public.group_members for all
    using (public.is_group_owner(public.group_members.group_id))
    with check (public.is_group_owner(public.group_members.group_id));

-- A trainee sees rows addressed to them, by id or by e-mail: the invitation
-- may predate their sign-up, in which case user_id is still null.
drop policy if exists "members: invitee reads own" on public.group_members;
create policy "members: invitee reads own"
    on public.group_members for select
    using (
        user_id = auth.uid()
        or lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
    );

-- Accepting an invitation.
drop policy if exists "members: invitee updates own" on public.group_members;
create policy "members: invitee updates own"
    on public.group_members for update
    using (
        user_id = auth.uid()
        or lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
    )
    with check (
        user_id = auth.uid()
        or lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
    );

-- Leaving a group.
drop policy if exists "members: invitee leaves" on public.group_members;
create policy "members: invitee leaves"
    on public.group_members for delete
    using (user_id = auth.uid());

-- --- quizzes ----------------------------------------------------------------
drop policy if exists "quizzes: owner full access" on public.quizzes;
create policy "quizzes: owner full access"
    on public.quizzes for all
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

drop policy if exists "quizzes: readable when shared with my group" on public.quizzes;
create policy "quizzes: readable when shared with my group"
    on public.quizzes for select
    using (public.quiz_shared_with_me(public.quizzes.id));

-- --- quiz_shares ------------------------------------------------------------
drop policy if exists "shares: group owner manages" on public.quiz_shares;
create policy "shares: group owner manages"
    on public.quiz_shares for all
    using (public.is_group_owner(public.quiz_shares.group_id))
    with check (public.is_group_owner(public.quiz_shares.group_id));

drop policy if exists "shares: members can read" on public.quiz_shares;
create policy "shares: members can read"
    on public.quiz_shares for select
    using (public.is_group_member(public.quiz_shares.group_id));

-- ===========================================================================
-- 4. New auth user -> profile row
-- ===========================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    signup_role text;
begin
    signup_role := coalesce(new.raw_user_meta_data ->> 'role', 'trainee');
    if signup_role not in ('trainer', 'trainee') then
        signup_role := 'trainee';
    end if;

    insert into public.profiles (id, email, first_name, last_name, role, active_view)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data ->> 'first_name', ''),
        coalesce(new.raw_user_meta_data ->> 'last_name', ''),
        signup_role,
        signup_role
    )
    on conflict (id) do nothing;

    -- Invitations sent before this person signed up are addressed by e-mail
    -- only; bind them to the new account now.
    update public.group_members
       set user_id = new.id
     where user_id is null
       and lower(email) = lower(new.email);

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ===========================================================================
-- 5. Table privileges
--
-- RLS decides which rows a user may touch; these GRANTs decide whether the
-- role may touch the table at all. Both are needed — without the grant every
-- query fails with "permission denied", regardless of the policies.
--
-- Tables created through the SQL editor do not get these automatically (the
-- dashboard's table builder adds them behind the scenes), so they are spelled
-- out here.
--
-- Deliberately no grants for `anon`: everything in this schema belongs to a
-- signed-in user. Anonymous visitors use the app in offline mode, which never
-- touches the backend.
-- ===========================================================================

grant usage on schema public to authenticated;

grant select, insert, update, delete on public.profiles      to authenticated;
grant select, insert, update, delete on public.groups         to authenticated;
grant select, insert, update, delete on public.group_members  to authenticated;
grant select, insert, update, delete on public.quizzes        to authenticated;
grant select, insert, update, delete on public.quiz_shares    to authenticated;

grant execute on function public.is_group_owner(uuid)       to authenticated;
grant execute on function public.is_group_member(uuid)      to authenticated;
grant execute on function public.shares_a_group_with(uuid)  to authenticated;
grant execute on function public.quiz_shared_with_me(uuid)  to authenticated;
