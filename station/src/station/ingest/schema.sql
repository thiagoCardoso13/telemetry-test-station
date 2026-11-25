CREATE TABLE IF NOT EXISTS telemetry_sample (
    time      timestamptz      NOT NULL,
    parameter text             NOT NULL,
    value     double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS telemetry_sample_by_parameter ON telemetry_sample (parameter, time);
CREATE INDEX IF NOT EXISTS telemetry_sample_by_time ON telemetry_sample (time);

CREATE TABLE IF NOT EXISTS packet_log (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    time       timestamptz NOT NULL,
    direction  text        NOT NULL,
    service    integer,
    subservice integer,
    sequence   integer,
    valid      boolean     NOT NULL,
    detail     text        NOT NULL
);
CREATE INDEX IF NOT EXISTS packet_log_by_time ON packet_log (time);

CREATE TABLE IF NOT EXISTS command (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sent_at    timestamptz NOT NULL,
    updated_at timestamptz,
    request_id bytea       NOT NULL,
    name       text        NOT NULL,
    args       jsonb       NOT NULL,
    status     text        NOT NULL DEFAULT 'sent',
    error      integer
);

CREATE TABLE IF NOT EXISTS alarm (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parameter  text             NOT NULL,
    bound      text             NOT NULL,
    value      double precision NOT NULL,
    raised_at  timestamptz      NOT NULL,
    cleared_at timestamptz
);

CREATE TABLE IF NOT EXISTS link_counter (
    name  text   PRIMARY KEY,
    value bigint NOT NULL
);
