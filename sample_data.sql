-- Sample data for the Flight Management Database
-- Run after schema.sql. All times are UTC, stored as 'YYYY-MM-DD HH:MM'.
-- Scenario snapshot: 10:00 UTC on 1 October 2026, so earlier flights have
-- Landed / Departed and later ones are still Scheduled.
-- The airline (flight prefix XX) and all pilots are fictional.

PRAGMA foreign_keys = ON;

-- 13 destinations (airports). SIN has no flights, to show an airport with zero flights.
INSERT INTO DESTINATION (destination_id, airport_code, airport_name, city, country) VALUES
    (1,  'LHR', 'Heathrow Airport',                         'London',     'United Kingdom'),
    (2,  'MAN', 'Manchester Airport',                       'Manchester', 'United Kingdom'),
    (3,  'EDI', 'Edinburgh Airport',                        'Edinburgh',  'United Kingdom'),
    (4,  'BHX', 'Birmingham Airport',                       'Birmingham', 'United Kingdom'),
    (5,  'CDG', 'Paris Charles de Gaulle Airport',          'Paris',      'France'),
    (6,  'AMS', 'Amsterdam Airport Schiphol',               'Amsterdam',  'Netherlands'),
    (7,  'FRA', 'Frankfurt Airport',                        'Frankfurt',  'Germany'),
    (8,  'MAD', 'Adolfo Suárez Madrid–Barajas Airport',     'Madrid',     'Spain'),
    (9,  'FCO', 'Leonardo da Vinci–Fiumicino Airport',      'Rome',       'Italy'),
    (10, 'DUB', 'Dublin Airport',                           'Dublin',     'Ireland'),
    (11, 'JFK', 'John F. Kennedy International Airport',    'New York',   'United States'),
    (12, 'DXB', 'Dubai International Airport',              'Dubai',      'United Arab Emirates'),
    (13, 'SIN', 'Singapore Changi Airport',                 'Singapore',  'Singapore');

-- 13 pilots: 6 Captains, 7 First Officers. Ryan Patel (13) has no assignments yet.
INSERT INTO PILOT (pilot_id, licence_number, first_name, last_name, rank, hire_date) VALUES
    (1,  'UK-ATPL-100231', 'James',  'Carter',    'Captain',       '2009-03-16'),
    (2,  'UK-ATPL-100587', 'Priya',  'Sharma',    'Captain',       '2011-07-04'),
    (3,  'UK-ATPL-100142', 'Thomas', 'Hughes',    'Captain',       '2008-01-21'),
    (4,  'UK-ATPL-101093', 'Aisha',  'Bello',     'Captain',       '2013-09-09'),
    (5,  'UK-ATPL-101456', 'Marco',  'Rossi',     'Captain',       '2015-05-18'),
    (6,  'UK-ATPL-101322', 'Sophie', 'Turner',    'Captain',       '2014-02-03'),
    (7,  'UK-ATPL-102718', 'Liam',   'O''Connor', 'First Officer', '2019-06-10'),
    (8,  'UK-ATPL-103004', 'Wei',    'Chen',      'First Officer', '2020-09-14'),
    (9,  'UK-ATPL-103361', 'Emma',   'Walsh',     'First Officer', '2021-01-25'),
    (10, 'UK-ATPL-102490', 'Hannah', 'Schmidt',   'First Officer', '2018-11-05'),
    (11, 'UK-ATPL-103775', 'Omar',   'Haddad',    'First Officer', '2022-03-28'),
    (12, 'UK-ATPL-104112', 'Grace',  'Kim',       'First Officer', '2023-08-14'),
    (13, 'UK-ATPL-104598', 'Ryan',   'Patel',     'First Officer', '2024-01-15');

-- 15 flights across 30 September - 3 October 2026.
-- Durations follow typical scheduled times for each route.
-- XX101 and XX001 repeat on different days (same flight_number, different flight_id).
-- Flights 5 and 11 arrive the day after they depart (overnight).
INSERT INTO FLIGHT (flight_id, flight_number, origin_id, destination_id, departure_datetime, arrival_datetime, status) VALUES
    (1,  'XX101', 1,  5,  '2026-09-30 07:30', '2026-09-30 08:45', 'Landed'),     -- LHR -> CDG  1h 15m
    (2,  'XX102', 5,  1,  '2026-09-30 10:00', '2026-09-30 11:15', 'Landed'),     -- CDG -> LHR  1h 15m
    (3,  'XX201', 1,  3,  '2026-09-30 18:00', '2026-09-30 19:25', 'Landed'),     -- LHR -> EDI  1h 25m
    (4,  'XX001', 1,  11, '2026-09-30 11:00', '2026-09-30 19:05', 'Landed'),     -- LHR -> JFK  8h 05m
    (5,  'XX002', 11, 1,  '2026-09-30 23:30', '2026-10-01 06:20', 'Landed'),     -- JFK -> LHR  6h 50m (overnight)
    (6,  'XX301', 2,  6,  '2026-10-01 06:45', '2026-10-01 08:00', 'Landed'),     -- MAN -> AMS  1h 15m
    (7,  'XX101', 1,  5,  '2026-10-01 07:30', '2026-10-01 08:45', 'Landed'),     -- LHR -> CDG  1h 15m
    (8,  'XX401', 1,  7,  '2026-10-01 09:15', '2026-10-01 10:45', 'Departed'),   -- LHR -> FRA  1h 30m
    (9,  'XX211', 3,  10, '2026-10-01 10:30', '2026-10-01 11:40', 'Boarding'),   -- EDI -> DUB  1h 10m
    (10, 'XX601', 1,  8,  '2026-10-01 13:45', '2026-10-01 16:05', 'Delayed'),    -- LHR -> MAD  2h 20m
    (11, 'XX701', 1,  12, '2026-10-01 21:00', '2026-10-02 04:00', 'Scheduled'),  -- LHR -> DXB  7h 00m (overnight)
    (12, 'XX212', 10, 1,  '2026-10-02 07:00', '2026-10-02 08:20', 'Scheduled'),  -- DUB -> LHR  1h 20m
    (13, 'XX801', 1,  9,  '2026-10-02 12:30', '2026-10-02 15:00', 'Cancelled'),  -- LHR -> FCO  2h 30m
    (14, 'XX303', 6,  4,  '2026-10-03 09:00', '2026-10-03 10:10', 'Scheduled'),  -- AMS -> BHX  1h 10m
    (15, 'XX001', 1,  11, '2026-10-03 11:00', '2026-10-03 19:05', 'Scheduled');  -- LHR -> JFK  8h 05m

-- 28 assignments. Every rostered flight has a full crew (a Captain and a First Officer).
-- Flight 15 is not rostered yet, so it has no crew and appears in "flights needing crew".
-- The triggers in schema.sql check every row: no pilot is on two overlapping flights,
-- and only Captain-rank pilots fly as Captain.
INSERT INTO FLIGHT_ASSIGNMENT (flight_id, pilot_id, role) VALUES
    (1,  1,  'Captain'), (1,  7,  'First Officer'),
    (2,  1,  'Captain'), (2,  7,  'First Officer'),
    (3,  2,  'Captain'), (3,  8,  'First Officer'),
    (4,  3,  'Captain'), (4,  10, 'First Officer'),
    (5,  4,  'Captain'), (5,  9,  'First Officer'),
    (6,  5,  'Captain'), (6,  11, 'First Officer'),
    (7,  6,  'Captain'), (7,  12, 'First Officer'),
    (8,  1,  'Captain'), (8,  7,  'First Officer'),
    (9,  2,  'Captain'), (9,  8,  'First Officer'),
    (10, 6,  'Captain'), (10, 12, 'First Officer'),
    (11, 4,  'Captain'), (11, 9,  'First Officer'),
    (12, 2,  'Captain'), (12, 8,  'First Officer'),
    (13, 1,  'Captain'), (13, 7,  'First Officer'),
    (14, 5,  'Captain'), (14, 11, 'First Officer');
