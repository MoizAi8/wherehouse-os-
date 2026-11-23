-- Run only against the separate warehouse_evaluation database as its owner.
DO $$ BEGIN
  IF current_database() <> 'warehouse_evaluation' OR current_user <> 'warehouse_evaluator' THEN
    RAISE EXCEPTION 'Wrong instructor database or role';
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.instructor_slots (
    slot smallint PRIMARY KEY CHECK (slot BETWEEN 0 AND 7), owner text UNIQUE,
    touched timestamptz, writes integer NOT NULL DEFAULT 0,
    run uuid, stage text, result jsonb, started timestamptz
);
INSERT INTO public.instructor_slots(slot) SELECT generate_series(0,7) ON CONFLICT DO NOTHING;
