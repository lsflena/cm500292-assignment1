import os
import re
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "flight_management.db")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")
SAMPLE_DATA_FILE = os.path.join(BASE_DIR, "sample_data.sql")
QUERIES_FILE = os.path.join(BASE_DIR, "queries.sql")

# Must match the CHECK constraints in schema.sql
STATUSES = ["Scheduled", "Delayed", "Boarding", "Departed", "Landed", "Cancelled"]
RANKS = ["Captain", "First Officer"]
ROLES = ["Captain", "First Officer"]
# Crew can't be changed on flights that are already underway, over or cancelled
CLOSED_STATUSES = ["Departed", "Landed", "Cancelled"]

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# Column headings shown to the user
HEADINGS = {
    "flight_id": "ID",
    "flight_number": "Flight",
    "origin": "From",
    "destination": "To",
    "departure_datetime": "Departure (UTC)",
    "arrival_datetime": "Arrival (UTC)",
    "duration": "Duration",
    "status": "Status",
    "captain": "Captain",
    "first_officer": "First Officer",
    "pilot_id": "Pilot ID",
    "pilot": "Pilot",
    "rank": "Rank",
    "role": "Role",
    "licence_number": "Licence",
    "hire_date": "Hired",
    "destination_id": "ID",
    "airport_code": "Code",
    "airport_name": "Airport",
    "city": "City",
    "country": "Country",
    "flights": "Flights",
    "hours": "Flying hours",
}

# ---------------------------------------------------------------------------
# Loading queries.sql
# ---------------------------------------------------------------------------

def load_queries(path):
    """Read queries.sql into a dictionary of {query name: SQL}."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    queries = {}
    name = None
    body = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(body).strip()
            name = stripped[len("-- name:"):].strip()
            body = []
        elif stripped.startswith("--"):
            continue
        elif name:
            body.append(line)
    if name:
        queries[name] = "\n".join(body).strip()
    return queries


# ---------------------------------------------------------------------------
# Input helpers to validate input
# ---------------------------------------------------------------------------

class Cancelled(Exception):
    """Raised when the user presses Enter on an empty answer to cancel an action."""


def read(prompt):
    """Read one answer; an empty answer cancels the current action."""
    value = input(prompt).strip()
    if not value:
        raise Cancelled
    return value


def ask_text(prompt, allow_blank=False):
    value = input(prompt).strip()
    if value:
        return value
    if allow_blank:
        return None
    raise Cancelled


def ask_int(prompt):
    while True:
        value = read(prompt)
        try:
            return int(value)
        except ValueError:
            print("  Please enter a whole number (or press Enter to cancel).")


def ask_airport_code(prompt, allow_blank=False):
    while True:
        value = input(prompt).strip().upper()
        if not value:
            if allow_blank:
                return None
            raise Cancelled
        if len(value) == 3 and value.isalpha():
            return value
        print("  Please enter a 3-letter airport code, e.g. LHR (or press Enter to cancel).")


def ask_flight_number(prompt):
    while True:
        value = read(prompt).upper()
        # Airline code (2 letters or digits) followed by 1-4 digits, e.g. XX101
        if re.fullmatch(r"[A-Z0-9]{2}\d{1,4}", value):
            return value
        print("  Please enter a flight number such as XX101 (or press Enter to cancel).")


def ask_date(prompt, allow_blank=False):
    while True:
        value = input(prompt).strip()
        if not value:
            if allow_blank:
                return None
            raise Cancelled
        try:
            return datetime.strptime(value, DATE_FORMAT).strftime(DATE_FORMAT)
        except ValueError:
            print("  Please enter a date as YYYY-MM-DD, e.g. 2026-10-01 (or press Enter to cancel).")


def ask_datetime(prompt, current=None):
    """Ask for a date and time. Pressing enter on a blank keeps to the current date and time."""
    while True:
        value = input(prompt).strip()
        if not value:
            if current:
                return current
            raise Cancelled
        try:
            return datetime.strptime(value, DATETIME_FORMAT).strftime(DATETIME_FORMAT)
        except ValueError:
            print("  Please enter a date and time as YYYY-MM-DD HH:MM, e.g. 2026-10-01 14:30"
                  " (or press Enter to cancel).")


def ask_time_window():
    """Ask for a start and end time and make sure the end time is after the start time."""
    start = ask_datetime("From (YYYY-MM-DD HH:MM, UTC): ")
    while True:
        end = ask_datetime("To   (YYYY-MM-DD HH:MM, UTC): ")
        if end > start:
            return start, end
        print("  The end must be after the start.")


def ask_choice(prompt, options, allow_blank=False):
    """Show a numbered list and return the option picked."""
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    while True:
        value = input(prompt).strip()
        if not value:
            if allow_blank:
                return None
            raise Cancelled
        if value.isdigit() and 1 <= int(value) <= len(options):
            return options[int(value) - 1]
        print(f"  Please enter a number from 1 to {len(options)} (or press Enter to cancel).")


def confirm(prompt):
    while True:
        value = read(prompt + " (y/n): ").lower()
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please enter y or n.")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_table(columns, rows):
    """Print query results as aligned columns."""
    if not rows:
        print("  No records found.")
        return
    headings = [HEADINGS.get(c, c.replace("_", " ").title()) for c in columns]
    numeric = [all(isinstance(row[i], (int, float)) for row in rows if row[i] is not None)
               for i in range(len(columns))]
    cells = [["" if v is None else str(v) for v in row] for row in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headings)]

    def line(values):
        return "  " + "  ".join(v.rjust(w) if num else v.ljust(w)
                                for v, w, num in zip(values, widths, numeric))

    print()
    print(line(headings))
    print("  " + "  ".join("-" * w for w in widths))
    for row in cells:
        print(line(row))
    print(f"\n  {len(rows)} record(s)")


def explain_db_error(error):
    """Display database error message."""
    message = str(error)
    known = [
        ("arrival_datetime > departure_datetime", "The arrival time must be after the departure time."),
        ("origin_id <> destination_id", "The origin and destination must be different airports."),
        ("FLIGHT_ASSIGNMENT.flight_id, FLIGHT_ASSIGNMENT.role", "This flight already has a pilot in that role."),
        ("FLIGHT_ASSIGNMENT.flight_id, FLIGHT_ASSIGNMENT.pilot_id", "This pilot is already assigned to this flight."),
        ("FLIGHT.flight_number, FLIGHT.departure_datetime", "A flight with this number already departs at that time."),
        ("DESTINATION.airport_code", "A destination with this airport code already exists."),
        ("length(airport_code) = 3", "The airport code must be 3 letters."),
        ("FLIGHT.origin_id", "Unknown origin airport code."),
        ("FLIGHT.destination_id", "Unknown destination airport code."),
        ("FOREIGN KEY constraint failed", "This refers to a pilot, flight or destination that doesn't exist, "
                                          "or to one that other records still depend on."),
    ]
    for fragment, text in known:
        if fragment in message:
            return text
    if message.endswith("."):
        return message
    return f"The database rejected this change ({message})."


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

class DBOperations:
    """Run the named queries from queries.sql against the database."""

    def __init__(self):
        self.queries = load_queries(QUERIES_FILE)
        first_run = not os.path.exists(DB_FILE)
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.execute("PRAGMA foreign_keys = ON")
        if first_run:
            self.create_database()

    def create_database(self):
        """Create the db tables and load the sample data on first run"""
        try:
            for path in (SCHEMA_FILE, SAMPLE_DATA_FILE):
                with open(path, encoding="utf-8") as f:
                    self.conn.executescript(f.read())
            self.conn.commit()
            print("New database created and loaded with sample data.")
        except (sqlite3.Error, OSError):
            self.conn.close()
            os.remove(DB_FILE)
            raise

    def close(self):
        self.conn.close()

    # --- running queries ---------------------------------------------------

    def fetch(self, name, **params):
        """Run a SELECT query and return column names and rows."""
        cursor = self.conn.execute(self.queries[name], params)
        columns = [d[0] for d in cursor.description]
        return columns, cursor.fetchall()

    def fetch_one(self, name, **params):
        """Run a SELECT query to return one row or none."""
        cursor = self.conn.execute(self.queries[name], params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(zip([d[0] for d in cursor.description], row))

    def show(self, name, **params):
        print_table(*self.fetch(name, **params))

    def write(self, name, **params):
        """Run an INSERT, UPDATE or DELETE."""
        try:
            cursor = self.conn.execute(self.queries[name], params)
            self.conn.commit()
            return cursor
        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            print("  " + explain_db_error(e))
            return None

    # --- shared lookups ----------------------------------------------------

    def get_flight(self, flight_id):
        """Return the flight as a dict, or None if it doesn't exist."""
        flight = self.fetch_one("flight_by_id", flight_id=flight_id)
        if flight is None:
            print(f"  No flight with ID {flight_id} was found.")
        return flight

    def get_destination(self, code):
        """Return the destination as a dict, or None if it doesn't exist."""
        destination = self.fetch_one("destination_by_code", airport_code=code)
        if destination is None:
            print(f"  No destination with airport code {code} was found.")
        return destination

    def get_pilot(self, pilot_id):
        """Return the pilot as a dict, or None."""
        columns, rows = self.fetch("search_pilot", term=str(pilot_id))
        for row in rows:
            if row[0] == pilot_id:
                return dict(zip(columns, row))
        print(f"  No pilot with ID {pilot_id} was found.")
        return None

    def find_pilot(self):
        """Search by pilot ID, name or licence number. Return the pilot or none."""
        term = ask_text("Pilot ID, name or licence number: ")
        columns, rows = self.fetch("search_pilot", term=term)
        if not rows:
            print("  No pilot matched.")
            return None
        if len(rows) > 1:
            print("  More than one pilot matched:")
            print_table(columns, rows)
            matches = {row[0]: row for row in rows}
            while True:
                pilot_id = ask_int("Pilot ID from the list: ")
                if pilot_id in matches:
                    return dict(zip(columns, matches[pilot_id]))
                print("  Please choose an ID from the list above.")
        return dict(zip(columns, rows[0]))

    def offer_to_open(self, rows, prompt, open_page):
        """After a list, let the user open one record by its ID."""
        if not rows:
            return
        valid = {str(row[0]).upper() for row in rows}
        while True:
            value = input(prompt).strip().upper()
            if not value:
                return
            if value in valid:
                open_page(value)
                return
            print("  Please enter one of the IDs listed above, or press Enter to go back.")

    def run_menu(self, title, options, header=None):
        """Show a numbered menu of (label, action) pairs until the user picks 0 (Back).
        If the user cancels an action by pressing Enter on an empty answer, they come back to previous menu.
        """
        while True:
            if header and header() is False:
                return
            print(f"\n-- {title} --")
            for number, (label, _) in enumerate(options, start=1):
                print(f" {number}. {label}")
            print(" 0. Back")
            choice = input("Choose: ").strip()
            if choice == "0":
                return
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                try:
                    if options[int(choice) - 1][1]() == "close":
                        return
                except Cancelled:
                    print("  Cancelled. Nothing was changed.")
            else:
                print("  Invalid choice.")

    # =======================================================================
    # 1. View Flights
    # =======================================================================

    def flights_menu(self):
        self.run_menu("View Flights", [
            ("All Flights", self.all_flights),
            ("Search Flights", self.search_flights_menu),
            ("Upcoming Flights Needing Crew", self.flights_needing_crew),
            ("Add a New Flight", self.add_flight),
        ])

    def list_flights_and_offer(self, name, **params):
        """Show a list of flights, then offer to open one."""
        columns, rows = self.fetch(name, **params)
        print_table(columns, rows)
        self.offer_to_open(rows, "Flight ID to open (Enter to go back): ",
                           lambda value: self.flight_page(int(value)))

    def all_flights(self):
        self.list_flights_and_offer("flights_all")

    def search_flights_menu(self):
        self.run_menu("Search Flights", [
            ("By Flight ID", self.open_flight_by_id),
            ("By Destination, Status and/or Departure Date", self.search_flights),
            ("Flights per Status", lambda: self.show("flights_per_status")),
        ])

    def open_flight_by_id(self):
        self.flight_page(ask_int("Flight ID: "))

    def search_flights(self):
        print("Leave any criterion blank to ignore it.")
        code = ask_airport_code("Destination airport code: ", allow_blank=True)
        print("Status:")
        status = ask_choice("Choose status (blank for any): ", STATUSES, allow_blank=True)
        departure_date = ask_date("Departure date (YYYY-MM-DD): ", allow_blank=True)
        self.list_flights_and_offer("flights_by_criteria", airport_code=code, status=status,
                                    departure_date=departure_date)

    def flights_needing_crew(self):
        self.list_flights_and_offer("flights_needing_crew")

    def add_flight(self):
        print("\n-- Add a New Flight --")
        print("(Press Enter on an empty answer at any time to cancel.)")
        flight_number = ask_flight_number("Flight number (e.g. XX101): ")

        origin = self.get_destination(ask_airport_code("Origin airport code: "))
        if origin is None:
            return
        destination = self.get_destination(ask_airport_code("Destination airport code: "))
        if destination is None:
            return

        departure = ask_datetime("Departure (YYYY-MM-DD HH:MM, UTC): ")
        arrival = ask_datetime("Arrival   (YYYY-MM-DD HH:MM, UTC): ")
        print("Status:")
        status = ask_choice("Choose status: ", STATUSES)

        cursor = self.write("add_flight", flight_number=flight_number,
                            origin_code=origin["airport_code"],
                            destination_code=destination["airport_code"],
                            departure=departure, arrival=arrival, status=status)
        if cursor:
            print(f"  Flight {flight_number} added with ID {cursor.lastrowid}.")
            try:
                open_now = confirm("Open its page now (e.g. to assign its crew)?")
            except Cancelled:
                open_now = False
            if open_now:
                self.flight_page(cursor.lastrowid)

    # ----------- the flight record page ------------------

    def flight_page(self, flight_id):
        if self.get_flight(flight_id) is None:
            return

        def header():
            flight = self.fetch_one("flight_by_id", flight_id=flight_id)
            if flight is None:
                return False
            print(f"\n===== Flight {flight['flight_number']} (ID {flight_id}) =====")
            print_table(list(flight.keys()), [list(flight.values())])

        self.run_menu("Flight Actions", [
            ("Update Schedule", lambda: self.update_flight(flight_id)),
            ("Edit Crew", lambda: self.edit_crew(flight_id)),
            ("Delete Flight", lambda: self.delete_flight(flight_id)),
        ], header=header)

    def edit_crew(self, flight_id):
        flight = self.get_flight(flight_id)
        if flight is None or self.crew_if_changeable(flight) is None:
            return

        def header():
            print(f"\nCrew of {flight['flight_number']}:")
            self.show("flight_crew", flight_id=flight_id)

        self.run_menu("Edit Crew", [
            ("Assign", lambda: self.assign_pilot(flight_id, mode="assign")),
            ("Replace", lambda: self.assign_pilot(flight_id, mode="replace")),
            ("Remove", lambda: self.remove_pilot(flight_id)),
        ], header=header)

    def update_flight(self, flight_id):
        flight = self.get_flight(flight_id)
        if flight is None:
            return
        # Times and status are changed together, e.g. a delay usually means new times.
        print("Press Enter to keep the current value.")
        departure = ask_datetime(f"New departure [{flight['departure_datetime']}]: ",
                                 current=flight["departure_datetime"])
        arrival = ask_datetime(f"New arrival   [{flight['arrival_datetime']}]: ",
                               current=flight["arrival_datetime"])
        print(f"Status [{flight['status']}]:")
        status = ask_choice("Choose new status (Enter to keep): ", STATUSES, allow_blank=True)
        cursor = self.write("update_flight", flight_id=flight_id,
                            departure=departure, arrival=arrival,
                            status=status or flight["status"])
        if cursor and cursor.rowcount:
            print("  Flight updated.")

    def delete_flight(self, flight_id):
        flight = self.get_flight(flight_id)
        if flight is None:
            return "close"
        if not confirm(f"Delete flight {flight['flight_number']} (ID {flight_id}) and its pilot assignments?"):
            print("  Nothing was deleted.")
            return None
        cursor = self.write("delete_flight", flight_id=flight_id)
        if cursor and cursor.rowcount:
            print("  Flight deleted.")
            return "close"
        return None

    # ----------- crew changes  ------------

    def crew_if_changeable(self, flight):
        """Return the flight's crew rows, or none if its crew can no longer be changed."""
        if flight["status"] in CLOSED_STATUSES:
            print(f"  The crew can't be changed on a flight that is {flight['status']}.")
            return None
        return self.fetch("flight_crew", flight_id=flight["flight_id"])[1]

    def assign_pilot(self, flight_id, pilot=None, mode=None):
        """Fill a role on a flight, or replace the assigned pilot. Make sure that assigned role matches the pilot rank."""
        flight = self.get_flight(flight_id)
        if flight is None:
            return
        crew = self.crew_if_changeable(flight)
        if crew is None:
            return
        current = {row[3]: row[1] for row in crew}

        if mode == "assign":
            roles = [role for role in ROLES if role not in current]
            if not roles:
                print("  This flight already has a full crew. Use Replace to change a pilot.")
                return
            options = roles
        elif mode == "replace":
            roles = [role for role in ROLES if role in current]
            if not roles:
                print("  This flight has no crew yet. Use Assign to add a pilot.")
                return
            options = [f"{role} ({current[role]})" for role in roles]
        else:
            roles = ROLES
            options = [f"{role} ({current[role]})" if role in current else f"{role} (empty)"
                       for role in ROLES]
        print("Role:")
        role = roles[options.index(ask_choice("Choose role: ", options))]

        if pilot is not None and role == "Captain" and pilot["rank"] != "Captain":
            print(f"  {pilot['pilot']} is a {pilot['rank']} and can't fly as Captain.")
            return
        if mode is None and role in current and not confirm(f"Replace {current[role]} as {role}?"):
            print("  Nothing was changed.")
            return

        if pilot is None:
            print(f"Pilots available to fly as {role} at that time:")
            self.show("pilots_by_criteria", rank="Captain" if role == "Captain" else None,
                      start=flight["departure_datetime"], end=flight["arrival_datetime"])
            pilot = self.find_pilot()
            if pilot is None:
                return
        if role == "Captain" and pilot["rank"] != "Captain":
            print(f"  {pilot['pilot']} is a {pilot['rank']} and can't fly as Captain.")
            return

        cursor = self.write("assign_pilot", flight_id=flight_id,
                            pilot_id=pilot["pilot_id"], role=role)
        if cursor:
            action = f"replaces {current[role]}" if role in current else "assigned"
            print(f"  {pilot['pilot']} {action} as {role} on {flight['flight_number']}.")

    def remove_pilot(self, flight_id, pilot_id=None):
        """Remove a pilot from a flight."""
        flight = self.get_flight(flight_id)
        if flight is None:
            return
        crew = self.crew_if_changeable(flight)
        if crew is None:
            return
        if not crew:
            print("  This flight has no crew to remove.")
            return
        if pilot_id is None:
            pilot_id = ask_int("Pilot ID to remove: ")
        if not confirm("Remove this pilot? The flight will be short of crew until someone is assigned."):
            print("  Nothing was changed.")
            return
        cursor = self.write("unassign_pilot", flight_id=flight_id, pilot_id=pilot_id)
        if cursor and cursor.rowcount:
            print(f"  Pilot removed from {flight['flight_number']}.")
        elif cursor:
            print(f"  Pilot {pilot_id} is not assigned to this flight.")

    # =======================================================================
    # 2. View Pilot Assignments
    # =======================================================================

    def pilots_menu(self):
        self.run_menu("View Pilot Assignments", [
            ("All Pilots", self.all_pilots),
            ("Search Pilots", self.search_pilots_menu),
        ])

    def list_pilots_and_offer(self, name, **params):
        """Show a list of pilots and give option to open one by its ID."""
        columns, rows = self.fetch(name, **params)
        print_table(columns, rows)
        self.offer_to_open(rows, "Pilot ID to open (Enter to go back): ",
                           lambda value: self.pilot_page(int(value)))

    def all_pilots(self):
        self.list_pilots_and_offer("pilots_all")

    def search_pilots_menu(self):
        self.run_menu("Search Pilots", [
            ("By ID, Name or Licence Number", self.open_pilot_by_search),
            ("By Rank and/or Availability", self.search_pilots),
        ])

    def open_pilot_by_search(self):
        pilot = self.find_pilot()
        if pilot:
            self.pilot_page(pilot["pilot_id"])

    def search_pilots(self):
        print("Leave any criterion blank to ignore it.")
        print("Rank:")
        rank = ask_choice("Choose rank (blank for any): ", RANKS, allow_blank=True)
        start = end = None
        if confirm("Only show pilots free during a time window?"):
            start, end = ask_time_window()
        self.list_pilots_and_offer("pilots_by_criteria", rank=rank, start=start, end=end)

    # ------------ the pilot records page --------------

    def pilot_page(self, pilot_id):
        if self.get_pilot(pilot_id) is None:
            return

        def header():
            pilot = self.get_pilot(pilot_id)
            print(f"\n===== {pilot['pilot']} (ID {pilot_id}) =====")
            print_table(list(pilot.keys()), [list(pilot.values())])
            print("Schedule:")
            self.show("pilot_schedule", pilot_id=pilot_id)

        self.run_menu("Pilot Actions", [
            ("Assign This Pilot to a Flight",
             lambda: self.assign_pilot(ask_int("Flight ID: "), pilot=self.get_pilot(pilot_id))),
            ("Remove This Pilot from a Flight",
             lambda: self.remove_pilot(ask_int("Flight ID: "), pilot_id=pilot_id)),
        ], header=header)

    # =======================================================================
    # 3. View Destinations
    # =======================================================================

    def destinations_menu(self):
        self.run_menu("View Destinations", [
            ("All Destinations", self.all_destinations),
            ("Search Destinations", self.search_destinations_menu),
            ("Add a Destination", self.add_destination),
        ])

    def list_destinations_and_offer(self, name, **params):
        """Show a list of destinations and give option to open one by its ID."""
        columns, rows = self.fetch(name, **params)
        print_table(columns, rows)
        code_for_id = {str(row[0]): row[1] for row in rows}
        self.offer_to_open(rows, "Destination ID to open (Enter to go back): ",
                           lambda value: self.destination_page(code_for_id[value]))

    def all_destinations(self):
        self.list_destinations_and_offer("destinations_all")

    def search_destinations_menu(self):
        self.run_menu("Search Destinations", [
            ("By Airport Code", lambda: self.destination_page(ask_airport_code("Airport code: "))),
            ("By City or Country", lambda: self.list_destinations_and_offer(
                "destinations_by_location", term=ask_text('City or country (full or partial name, e.g. "paris" or "united"): '))),
        ])

    def add_destination(self):
        print("\n-- Add a Destination --")
        print("(Press Enter on an empty answer at any time to cancel.)")
        code = ask_airport_code("New airport code (3 letters): ")
        name = ask_text("Airport name: ")
        city = ask_text("City: ")
        country = ask_text("Country: ")
        cursor = self.write("add_destination", airport_code=code, airport_name=name,
                            city=city, country=country)
        if cursor:
            print(f"  Destination {code} added.")

    # ------------- the destination records page ---------------

    def destination_page(self, code):
        if self.get_destination(code) is None:
            return
        page = {"code": code}

        def header():
            destination = self.get_destination(page["code"])
            print(f"\n===== {destination['airport_code']}: {destination['airport_name']} =====")
            print_table(list(destination.keys()), [list(destination.values())])
            print("Flights to this destination:")
            self.show("flights_by_criteria", airport_code=page["code"],
                      status=None, departure_date=None)

        def update():
            new_code = self.update_destination(page["code"])
            if new_code:
                page["code"] = new_code

        self.run_menu("Destination Actions", [
            ("Update This Destination", update),
        ], header=header)

    def update_destination(self, code):
        """Edit a destination's details."""
        destination = self.get_destination(code)
        if destination is None:
            return None
        print("Press Enter to keep the current value.")
        new_code = ask_airport_code(f"Airport code [{destination['airport_code']}]: ", allow_blank=True)
        name = ask_text(f"Airport name [{destination['airport_name']}]: ", allow_blank=True)
        city = ask_text(f"City [{destination['city']}]: ", allow_blank=True)
        country = ask_text(f"Country [{destination['country']}]: ", allow_blank=True)
        cursor = self.write("update_destination", destination_id=destination["destination_id"],
                            airport_code=new_code or destination["airport_code"],
                            airport_name=name or destination["airport_name"],
                            city=city or destination["city"],
                            country=country or destination["country"])
        if cursor and cursor.rowcount:
            print("  Destination updated.")
            return new_code or destination["airport_code"]
        return None


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main():
    db_ops = DBOperations()
    actions = {
        "1": db_ops.flights_menu,
        "2": db_ops.pilots_menu,
        "3": db_ops.destinations_menu,
    }
    try:
        while True:
            print("\n===== Flight Management System =====")
            print(" 1. View Flights")
            print(" 2. View Pilot Assignments")
            print(" 3. View Destinations")
            print(" 0. Exit")
            choice = input("Enter your choice: ").strip()

            if choice == "0":
                break
            if choice in actions:
                actions[choice]()
            else:
                print("  Invalid choice. Please enter a number from the menu.")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        db_ops.close()
        print("Goodbye.")


if __name__ == "__main__":
    main()
