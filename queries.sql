-- =====================================================================
-- 1. FLIGHT INFO RETRIEVAL AND MODIFICATION
-- =====================================================================

-- name: flights_all
-- See all flights
SELECT *
FROM FLIGHT_DETAILS
ORDER BY departure_datetime;

-- name: flights_by_criteria
-- See flights based on a combination of criteria (e.g., destination, status and date)
-- Pass NULL for any criterion to ignore it
SELECT *
FROM FLIGHT_DETAILS
WHERE (:airport_code IS NULL OR destination = :airport_code)
  AND (:status       IS NULL OR status = :status)
  AND (:departure_date IS NULL OR (departure_datetime >= :departure_date
                                   AND departure_datetime < date(:departure_date, '+1 day')))
ORDER BY departure_datetime;

-- name: flight_by_id
-- See a specific flight by its flight_id
SELECT *
FROM FLIGHT_DETAILS
WHERE flight_id = :flight_id;

-- name: flight_crew
-- See the pilots assigned to the flight
SELECT p.pilot_id, p.first_name || ' ' || p.last_name AS pilot, p.rank, a.role
FROM FLIGHT_ASSIGNMENT a
JOIN PILOT p ON p.pilot_id = a.pilot_id
WHERE a.flight_id = :flight_id
ORDER BY CASE a.role WHEN 'Captain' THEN 1 ELSE 2 END;


-- name: flights_needing_crew
-- See upcoming flights (not yet departed or cancelled) that do not have a full crew.
SELECT *
FROM FLIGHT_DETAILS
WHERE status IN ('Scheduled', 'Delayed', 'Boarding')
  AND (captain IS NULL OR first_officer IS NULL)
ORDER BY departure_datetime;

-- name: add_flight
-- Add a new flight
INSERT INTO FLIGHT (flight_number, origin_id, destination_id,
                    departure_datetime, arrival_datetime, status)
VALUES (:flight_number,
        (SELECT destination_id FROM DESTINATION WHERE airport_code = :origin_code),
        (SELECT destination_id FROM DESTINATION WHERE airport_code = :destination_code),
        :departure, :arrival, :status);

-- name: update_flight
-- Change flight status, and/or departure and arrival times
UPDATE FLIGHT
SET departure_datetime = :departure,
    arrival_datetime   = :arrival,
    status             = :status
WHERE flight_id = :flight_id;

-- name: delete_flight
-- Remove a flight
DELETE FROM FLIGHT
WHERE flight_id = :flight_id;

-- name: flights_per_status
-- See the number of flights in each status
SELECT status, COUNT(*) AS flights
FROM FLIGHT
GROUP BY status
ORDER BY flights DESC, status;

-- =====================================================================
-- 2. PILOT INFO RETRIEVAL AND ASSIGNMENT
-- =====================================================================

-- Every pilot listing also shows two summary figures calculated per pilot:
--   flights = number of flights the pilot is assigned to 
--   hours   = total scheduled flying hours, excluding cancelled flights

-- name: pilots_all
-- See all pilots, with their number of flights and flying hours
SELECT p.pilot_id, p.first_name || ' ' || p.last_name AS pilot, p.rank, p.licence_number, p.hire_date,
       (SELECT COUNT(*) FROM FLIGHT_ASSIGNMENT a WHERE a.pilot_id = p.pilot_id) AS flights,
       (SELECT ROUND(COALESCE(SUM((julianday(f.arrival_datetime) - julianday(f.departure_datetime)) * 24), 0), 1)
          FROM FLIGHT_ASSIGNMENT a JOIN FLIGHT f ON f.flight_id = a.flight_id
         WHERE a.pilot_id = p.pilot_id AND f.status <> 'Cancelled') AS hours
FROM PILOT p
ORDER BY p.last_name, p.first_name;

-- name: search_pilot
-- See a specific pilot by ID, name or licence number
SELECT p.pilot_id, p.first_name || ' ' || p.last_name AS pilot, p.rank, p.licence_number, p.hire_date,
       (SELECT COUNT(*) FROM FLIGHT_ASSIGNMENT a WHERE a.pilot_id = p.pilot_id) AS flights,
       (SELECT ROUND(COALESCE(SUM((julianday(f.arrival_datetime) - julianday(f.departure_datetime)) * 24), 0), 1)
          FROM FLIGHT_ASSIGNMENT a JOIN FLIGHT f ON f.flight_id = a.flight_id
         WHERE a.pilot_id = p.pilot_id AND f.status <> 'Cancelled') AS hours
FROM PILOT p
WHERE CAST(p.pilot_id AS TEXT) = :term
   OR UPPER(p.licence_number) = UPPER(:term)
   OR p.first_name || ' ' || p.last_name LIKE '%' || :term || '%'
ORDER BY p.last_name, p.first_name;

-- name: pilots_by_criteria
-- See pilots based on either rank and/or availability during a time window
-- Pass NULL for any criterion to ignore it
SELECT p.pilot_id, p.first_name || ' ' || p.last_name AS pilot, p.rank, p.licence_number, p.hire_date,
       (SELECT COUNT(*) FROM FLIGHT_ASSIGNMENT a WHERE a.pilot_id = p.pilot_id) AS flights,
       (SELECT ROUND(COALESCE(SUM((julianday(f.arrival_datetime) - julianday(f.departure_datetime)) * 24), 0), 1)
          FROM FLIGHT_ASSIGNMENT a JOIN FLIGHT f ON f.flight_id = a.flight_id
         WHERE a.pilot_id = p.pilot_id AND f.status <> 'Cancelled') AS hours
FROM PILOT p
WHERE (:rank IS NULL OR p.rank = :rank)
  AND (:start IS NULL OR NOT EXISTS (
      SELECT 1
      FROM FLIGHT_ASSIGNMENT a
      JOIN FLIGHT f ON f.flight_id = a.flight_id
      WHERE a.pilot_id = p.pilot_id
        AND f.status <> 'Cancelled'
        AND f.departure_datetime < :end
        AND :start < f.arrival_datetime))
ORDER BY p.rank, p.last_name, p.first_name;

-- name: pilot_schedule
-- See a specific pilot’s flights 
SELECT fd.flight_id, fd.flight_number, fd.origin, fd.destination,
       fd.departure_datetime, fd.arrival_datetime, fd.duration, fd.status, a.role
FROM FLIGHT_ASSIGNMENT a
JOIN FLIGHT_DETAILS fd ON fd.flight_id = a.flight_id
WHERE a.pilot_id = :pilot_id
ORDER BY fd.departure_datetime;

-- name: assign_pilot
-- Assign a pilot to a role on a flight
-- If the role is already filled, the new pilot replaces the current one
-- The same pilot cannot hold both roles
INSERT INTO FLIGHT_ASSIGNMENT (flight_id, pilot_id, role)
VALUES (:flight_id, :pilot_id, :role)
ON CONFLICT (flight_id, role) DO UPDATE SET pilot_id = excluded.pilot_id;

-- name: unassign_pilot
-- Remove a pilot from a flight
DELETE FROM FLIGHT_ASSIGNMENT
WHERE flight_id = :flight_id AND pilot_id = :pilot_id;


-- =====================================================================
-- 3. DESTINATION MANAGEMENT
-- =====================================================================

-- Every destination listing also shows a summary figure, calculated per destination:
--   flights = number of flights arriving at that destination

-- name: destinations_all
-- See all destinations, with their number of flights
SELECT d.destination_id, d.airport_code, d.airport_name, d.city, d.country,
       (SELECT COUNT(*) FROM FLIGHT f WHERE f.destination_id = d.destination_id) AS flights
FROM DESTINATION d
ORDER BY d.country, d.city;

-- name: destination_by_code
-- See a specific destination by airport code
SELECT d.destination_id, d.airport_code, d.airport_name, d.city, d.country,
       (SELECT COUNT(*) FROM FLIGHT f WHERE f.destination_id = d.destination_id) AS flights
FROM DESTINATION d
WHERE d.airport_code = :airport_code;

-- name: destinations_by_location
-- See destinations by city or country
SELECT d.destination_id, d.airport_code, d.airport_name, d.city, d.country,
       (SELECT COUNT(*) FROM FLIGHT f WHERE f.destination_id = d.destination_id) AS flights
FROM DESTINATION d
WHERE d.city LIKE '%' || :term || '%'
   OR d.country LIKE '%' || :term || '%'
ORDER BY d.country, d.city;

-- name: add_destination
-- Add a new destination
INSERT INTO DESTINATION (airport_code, airport_name, city, country)
VALUES (:airport_code, :airport_name, :city, :country);

-- name: update_destination
-- Update a destination's details
UPDATE DESTINATION
SET airport_code = :airport_code,
    airport_name = :airport_name,
    city         = :city,
    country      = :country
WHERE destination_id = :destination_id;