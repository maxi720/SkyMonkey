-- Track when a quiz was last changed. A trigger keeps updated_at current on
-- every UPDATE, so it is reliable no matter which code path saves the quiz
-- (editor, note edit, CSV re-import). Existing rows start equal to created_at.

alter table public.quizzes
    add column if not exists updated_at timestamptz not null default now();

update public.quizzes
    set updated_at = created_at
    where updated_at < created_at;

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists quizzes_touch_updated_at on public.quizzes;
create trigger quizzes_touch_updated_at
    before update on public.quizzes
    for each row
    execute function public.touch_updated_at();
