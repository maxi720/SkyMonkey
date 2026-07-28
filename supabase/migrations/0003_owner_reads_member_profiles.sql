-- Let a trainer read the profiles (names) of people in the groups they own.
--
-- The group owner is not themselves a group_members row, so the 0001
-- "fellow group members" policy does not cover them, and the group detail
-- page could only show member e-mails, not names.
--
-- Re-runnable.

-- True when `member` is a member (invited or accepted) of any group owned by
-- the current user. SECURITY DEFINER so the inner read is not re-filtered by
-- RLS (which would otherwise recurse through group_members' own policies).
create or replace function public.is_member_of_my_group(member uuid)
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
        where g.owner_id = auth.uid()
          and gm.user_id = member
    );
$$;

grant execute on function public.is_member_of_my_group(uuid) to authenticated;

drop policy if exists "profiles: owner reads group members" on public.profiles;
create policy "profiles: owner reads group members"
    on public.profiles for select
    using (public.is_member_of_my_group(public.profiles.id));
