-- Optional free-text notes a trainer can attach to a quiz (e.g. where the
-- questions come from, what to emphasise). Nullable, so existing quizzes and
-- the mobile app's SELECTs are unaffected. RLS already covers the quizzes
-- table, so no new policies are needed for another column.

alter table public.quizzes
    add column if not exists notes text;
