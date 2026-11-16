-- Log of every answer the assistant gives, plus the user's 👍/👎.
--
-- No usernames or IP addresses are stored. Ids are random UUIDs so the
-- public /feedback endpoint can't be used to rate answers by guessing ids.

CREATE TABLE answers (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  timestamptz NOT NULL DEFAULT now(),
    question    text NOT NULL,
    answer      text NOT NULL,
    sources     jsonb NOT NULL DEFAULT '[]',    -- [{"title": ..., "url": ...}]
    tool_calls  jsonb NOT NULL DEFAULT '[]',    -- [{"name": ..., "args": {...}}]
    model       text NOT NULL,
    latency_ms  integer NOT NULL CHECK (latency_ms >= 0),
    rating      smallint CHECK (rating IN (-1, 1)),
    comment     text,
    rated_at    timestamptz
);

-- For exporting rated (especially 👎) answers into the eval.
CREATE INDEX answers_rated ON answers (rated_at) WHERE rating IS NOT NULL;
