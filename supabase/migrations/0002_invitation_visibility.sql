-- Let an *invited* (not yet accepted) trainee see enough to decide on the
-- invitation: the group's name and the inviting trainer's name.
--
-- The 0001 policies only let *accepted* members read a group, and only fellow
-- members read each other's profiles. An invitation is shown before the person
-- is a member, so without this migration the invitation banner would show
-- blank group and trainer names.
--
-- Re-runnable: guarded with create-or-replace and drop-if-exists.

-- Any membership row for the current user (invited OR accepted). Kept separate
-- from is_group_member (which requires 'accepted') so existing checks are
-- unchanged. SECURITY DEFINER so the inner read does not re-trigger RLS.
create or replace function public.has_group_membership(gid uuid)
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
    );
$$;

-- True when `owner` owns a group the current user has any membership row in.
-- Used to reveal the inviting trainer's name to an invited trainee.
create or replace function public.owns_group_i_belong_to(owner uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
    select exists (
        select 1
        from public.groups g
        join public.group_members gm on gm.group_id = g.id
        where g.owner_id = owner
          and gm.user_id = auth.uid()
    );
$$;

grant execute on function public.has_group_membership(uuid) to authenticated;
grant execute on function public.owns_group_i_belong_to(uuid) to authenticated;

-- Groups: replace the accepted-only read with any-membership read, so an
-- invited trainee can see the group name too.
drop policy if exists "groups: members can read" on public.groups;
create policy "groups: members can read"
    on public.groups for select
    using (public.has_group_membership(public.groups.id));

-- Profiles: an invited or accepted member may read the group owner's profile.
drop policy if exists "profiles: read inviting trainer" on public.profiles;
create policy "profiles: read inviting trainer"
    on public.profiles for select
    using (public.owns_group_i_belong_to(public.profiles.id));
