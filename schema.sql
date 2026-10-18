PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS DESTINATION (
    destination_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    airport_code    TEXT    NOT NULL UNIQUE CHECK (length(airport_code) = 3),
    airport_name    TEXT    NOT NULL,
    city            TEXT    NOT NULL,
    country         TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS PILOT (
    pilot_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    licence_number  TEXT    NOT NULL UNIQUE,
    first_name      TEXT    NOT NULL,
    last_name       TEXT    NOT NULL,
    rank            TEXT    NOT NULL CHECK (rank IN ('Captain', 'First Officer')),
    hire_date       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS FLIGHT (
    flight_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_number       TEXT    NOT NULL,
    origin_id           INTEGER NOT NULL REFERENCES DESTINATION(destination_id) ON DELETE RESTRICT,
    destination_id      INTEGER NOT NULL REFERENCES DESTINATION(destination_id) ON DELETE RESTRICT,
    departure_datetime  TEXT    NOT NULL,
    arrival_datetime    TEXT    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'Scheduled'
                        CHECK (status IN ('Scheduled', 'Delayed', 'Boarding', 'Departed', 'Landed', 'Cancelled')),
    CHECK (origin_id <> destination_id),
    CHECK (arrival_datetime > departure_datetime),
    UNIQUE (flight_number, departure_datetime)
);

CREATE TABLE IF NOT EXISTS FLIGHT_ASSIGNMENT (
    flight_id   INTEGER NOT NULL REFERENCES FLIGHT(flight_id) ON DELETE CASCADE,
    pilot_id    INTEGER NOT NULL REFERENCES PILOT(pilot_id)   ON DELETE RESTRICT,
    role        TEXT    NOT NULL CHECK (role IN ('Captain', 'First Officer')),
    PRIMARY KEY (flight_id, pilot_id),
    UNIQUE (flight_id, role)
);

CREATE INDEX IF NOT EXISTS idx_flight_destination ON FLIGHT(destination_id);
CREATE INDEX IF NOT EXISTS idx_flight_departure   ON FLIGHT(departure_datetime);
CREATE INDEX IF NOT EXISTS idx_flight_status      ON FLIGHT(status);
CREATE INDEX IF NOT EXISTS idx_assignment_pilot   ON FLIGHT_ASSIGNMENT(pilot_id);

-- View: one row per flight, with airport codes, duration, and assigned crew.
-- Duration is derived from the two times rather than stored.
CREATE VIEW IF NOT EXISTS FLIGHT_DETAILS AS
SELECT f.flight_id, f.flight_number,
       o.airport_code AS origin, d.airport_code AS destination,
       f.departure_datetime, f.arrival_datetime,
       printf('%dh %02dm',
              CAST(ROUND((julianday(f.arrival_datetime) - julianday(f.departure_datetime)) * 1440) AS INTEGER) / 60,
              CAST(ROUND((julianday(f.arrival_datetime) - julianday(f.departure_datetime)) * 1440) AS INTEGER) % 60) AS duration,
       f.status,
       cp.first_name || ' ' || cp.last_name AS captain,
       fp.first_name || ' ' || fp.last_name AS first_officer
FROM FLIGHT f
JOIN DESTINATION o ON o.destination_id = f.origin_id
JOIN DESTINATION d ON d.destination_id = f.destination_id
LEFT JOIN FLIGHT_ASSIGNMENT ca ON ca.flight_id = f.flight_id AND ca.role = 'Captain'
LEFT JOIN PILOT cp             ON cp.pilot_id = ca.pilot_id
LEFT JOIN FLIGHT_ASSIGNMENT fa ON fa.flight_id = f.flight_id AND fa.role = 'First Officer'
LEFT JOIN PILOT fp             ON fp.pilot_id = fa.pilot_id;

-- Triggers: rules that need data from other rows, which a CHECK constraint can't see.

-- Only a Captain-rank pilot can fly as Captain
CREATE TRIGGER IF NOT EXISTS trg_assignment_rank_insert
BEFORE INSERT ON FLIGHT_ASSIGNMENT
WHEN NEW.role = 'Captain'
 AND (SELECT rank FROM PILOT WHERE pilot_id = NEW.pilot_id) <> 'Captain'
BEGIN
    SELECT RAISE(ABORT, 'Only a Captain-rank pilot can fly as Captain.');
END;

CREATE TRIGGER IF NOT EXISTS trg_assignment_rank_update
BEFORE UPDATE OF pilot_id, role ON FLIGHT_ASSIGNMENT
WHEN NEW.role = 'Captain'
 AND (SELECT rank FROM PILOT WHERE pilot_id = NEW.pilot_id) <> 'Captain'
BEGIN
    SELECT RAISE(ABORT, 'Only a Captain-rank pilot can fly as Captain.');
END;

-- A pilot can't be on two flights whose times overlap
CREATE TRIGGER IF NOT EXISTS trg_assignment_clash_insert
BEFORE INSERT ON FLIGHT_ASSIGNMENT
WHEN EXISTS (
    SELECT 1
    FROM FLIGHT f
    JOIN FLIGHT_ASSIGNMENT a ON a.pilot_id = NEW.pilot_id AND a.flight_id <> f.flight_id
    JOIN FLIGHT f2 ON f2.flight_id = a.flight_id
    WHERE f.flight_id = NEW.flight_id
      AND f.status <> 'Cancelled' AND f2.status <> 'Cancelled'
      AND f2.departure_datetime < f.arrival_datetime
      AND f.departure_datetime  < f2.arrival_datetime)
BEGIN
    SELECT RAISE(ABORT, 'This pilot is already on another flight at that time.');
END;

CREATE TRIGGER IF NOT EXISTS trg_assignment_clash_update
BEFORE UPDATE OF pilot_id, flight_id ON FLIGHT_ASSIGNMENT
WHEN EXISTS (
    SELECT 1
    FROM FLIGHT f
    JOIN FLIGHT_ASSIGNMENT a ON a.pilot_id = NEW.pilot_id AND a.flight_id <> f.flight_id
    JOIN FLIGHT f2 ON f2.flight_id = a.flight_id
    WHERE f.flight_id = NEW.flight_id
      AND f.status <> 'Cancelled' AND f2.status <> 'Cancelled'
      AND f2.departure_datetime < f.arrival_datetime
      AND f.departure_datetime  < f2.arrival_datetime)
BEGIN
    SELECT RAISE(ABORT, 'This pilot is already on another flight at that time.');
END;

-- Moving a flight's times must not double-book any assigned pilot
CREATE TRIGGER IF NOT EXISTS trg_flight_times_clash
BEFORE UPDATE OF departure_datetime, arrival_datetime ON FLIGHT
WHEN NEW.status <> 'Cancelled' AND EXISTS (
    SELECT 1
    FROM FLIGHT_ASSIGNMENT a
    JOIN FLIGHT_ASSIGNMENT b ON b.pilot_id = a.pilot_id AND b.flight_id <> a.flight_id
    JOIN FLIGHT f2 ON f2.flight_id = b.flight_id
    WHERE a.flight_id = NEW.flight_id
      AND f2.status <> 'Cancelled'
      AND f2.departure_datetime < NEW.arrival_datetime
      AND NEW.departure_datetime < f2.arrival_datetime)
BEGIN
    SELECT RAISE(ABORT, 'The new times clash with another flight one of its pilots is on.');
END;
