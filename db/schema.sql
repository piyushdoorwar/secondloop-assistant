-- SecondLoop workflow state (PostgreSQL 16)

CREATE TABLE IF NOT EXISTS proposals (
  id            text PRIMARY KEY,
  kind          text NOT NULL
                CHECK (kind IN ('return', 'escalation')),
  case_id       text NOT NULL,
  store_id      text NOT NULL,
  requested_by  text NOT NULL,
  spec          jsonb NOT NULL,
  spec_digest   text NOT NULL,
  policy_version int,
  state         text NOT NULL DEFAULT 'pending'
                CHECK (state IN ('pending', 'approved',
                                 'rejected', 'expired')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  proposal_id  text PRIMARY KEY REFERENCES proposals(id),
  decided_by   text NOT NULL,
  decision     text NOT NULL
               CHECK (decision IN ('approved', 'rejected')),
  spec_digest  text NOT NULL,
  decided_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operations (
  id            text PRIMARY KEY,
  proposal_id   text UNIQUE NOT NULL
                REFERENCES proposals(id),
  kind          text NOT NULL,
  case_id       text NOT NULL,
  spec          jsonb NOT NULL,
  state         text NOT NULL
                CHECK (state IN ('ready', 'submitting',
                                 'confirmed', 'rejected',
                                 'unknown', 'needs_review')),
  detail        text,
  vendor_ref    text,
  attempts      int NOT NULL DEFAULT 0,
  lease_until   timestamptz,
  submitted_at  timestamptz,
  requested_by  text NOT NULL,
  approved_by   text NOT NULL,
  installation  text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One live return per case, whatever the callers do.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_return_per_case
  ON operations (case_id)
  WHERE kind = 'return'
    AND state IN ('ready', 'submitting',
                  'confirmed', 'unknown');

CREATE TABLE IF NOT EXISTS outbox (
  id            text PRIMARY KEY,
  operation_id  text NOT NULL REFERENCES operations(id),
  event_type    text NOT NULL,
  payload       jsonb NOT NULL,
  state         text NOT NULL DEFAULT 'pending'
                CHECK (state IN ('pending', 'delivered',
                                 'unknown', 'needs_review')),
  attempts      int NOT NULL DEFAULT 0,
  vendor_ref    text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
