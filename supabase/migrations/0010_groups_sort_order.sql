-- ===========================================================================
-- Groups: add sort_order column for drag-and-drop reordering.
--
-- sort_order is nullable (NULL = not yet sorted, treated as last). The web app
-- orders by sort_order ASC NULLS LAST, then created_at as a tiebreaker.
-- The authenticated role needs UPDATE on the column; the existing RLS policy
-- on groups ("trainer owns group") already allows UPDATE for the owner.
-- ===========================================================================

alter table public.groups
    add column if not exists sort_order int;

create index if not exists groups_sort_idx on public.groups (owner_id, sort_order);
