import mysql.connector
from datetime import datetime
import os

# ====================== DATABASE CONNECTION ======================

def connect():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "air_cargo"),
            autocommit=False
        )
        print("Database connection established successfully")
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection failed: {err}")
        return None

# ====================== CUSTOMER FUNCTIONS ======================

def register_customer(cursor, conn):
    print("\n===== Register New Customer =====")
    errors = []
    
    customer_id = input("Enter Customer ID (upto 20 characters): ").strip()
    name = input("Enter Full Name: ").strip()
    email = input("Enter Email: ").strip()
    phone = input("Enter Phone (10 digits): ").strip()
    address = input("Enter Address: ").strip()
    password = input("Create a Password: ").strip()

    if not customer_id:
        errors.append("Customer ID cannot be empty")
    else:
        cursor.execute("SELECT CustomerID FROM customer WHERE CustomerID = %s", (customer_id,))
        if cursor.fetchone():
            errors.append("Customer ID already exists")

    if not email or '@' not in email:
        errors.append("Invalid email format")

    if not (phone.isdigit() and len(phone) == 10):
        errors.append("Phone must be exactly 10 digits")
        
    if not password:
        errors.append("Password cannot be empty")

    if errors:
        print("\nValidation Errors:")
        for error in errors:
            print(error)
        print("Registration rolled back due to errors")
        return None

    try:
        cursor.execute("""
            INSERT INTO customer (CustomerID, Name, Email, Phone, Address, PasswordHash)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (customer_id, name, email, phone, address, password))
        conn.commit()
        print("\nCustomer registered successfully!")
        return customer_id
    except mysql.connector.Error as err:
        print(f"\nDatabase Error: {err}")
        conn.rollback()
        return None

def update_customer_address(cursor, conn):
    print("\n===== Update Customer Address =====")
    customer_id = input("Enter your Customer ID: ").strip()
    if not customer_id:
        return

    try:
        cursor.execute("SELECT Name FROM customer WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        
        if not customer:
            print("Customer not found")
            return
            
        print(f"\nCurrent customer: {customer[0]}")
        new_address = input("Enter new address: ").strip()

        cursor.execute("UPDATE customer SET Address = %s WHERE CustomerID = %s", (new_address, customer_id))
        conn.commit()
        print("\nAddress updated successfully!")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"\nFailed to update address: {err}")

def delete_customer(cursor, conn):
    print("\n===== Delete Customer Account =====")
    customer_id = input("Enter your Customer ID: ").strip()
    if not customer_id:
        return

    try:
        cursor.execute("SELECT Name FROM customer WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        
        if not customer:
            print("Customer not found")
            return
            
        cursor.execute("""
            SELECT COUNT(*) FROM booking b 
            JOIN cargo c ON b.TrackingNumber = c.TrackingNumber 
            WHERE b.CustomerID = %s AND c.CurrentStatus != 'Delivered'
        """, (customer_id,))
        active_bookings = cursor.fetchone()[0]
        
        if active_bookings > 0:
            print(f"Cannot delete - customer has {active_bookings} active bookings")
            return

        confirm = input("\nAre you sure you want to delete this account? (yes/no): ").lower()
        if confirm == 'yes':
            cursor.execute("DELETE FROM customer WHERE CustomerID = %s", (customer_id,))
            conn.commit()
            print("\nCustomer account deleted successfully!")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"\nFailed to delete customer: {err}")

def book_cargo(cursor, conn, customer_id):
    print("\n===== Book Cargo Shipment =====")
    try:
        cursor.execute("""
            SELECT FlightID, OriginHub, DestinationHub, DepartureDate, AvailableCapacity
            FROM flight WHERE AvailableCapacity > 0 AND DepartureDate >= CURDATE()
            ORDER BY DepartureDate, OriginHub
        """)
        flights = cursor.fetchall()
        
        if not flights:
            print("\nNo available flights at this time.")
            return
        
        print("\nAvailable Flights:")
        for i, (fid, source, dest, date, space) in enumerate(flights, start=1):
            print(f" {i}. {source} -> {dest} | {date} | Capacity: {space}kg")

        choice = input("\nSelect flight (number) or type 0 to cancel: ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(flights):
            return
        
        flight_id, source, dest, date, space = flights[int(choice)-1]

        tracking_number = input("\nEnter new Tracking Number: ").strip()
        weight = float(input("Enter weight (kg): "))
        cargo_type = input("Enter cargo type: ").strip()
        
        if weight > space:
            print(f"Only {space}kg available on this flight.")
            return

        total_cost = weight * 5.0 # Basic cost calculation
        
        # Generate BookingID
        cursor.execute("SELECT COUNT(*) FROM booking")
        count = cursor.fetchone()[0]
        booking_id = f"BKG{count+1:03}"

        print("\nProcessing transaction...")
        cursor.execute("""
            INSERT INTO cargo (TrackingNumber, Weight, CargoType, TotalCost, CurrentStatus, CurrentLocation)
            VALUES (%s, %s, %s, %s, 'Booked', %s)
        """, (tracking_number, weight, cargo_type, total_cost, source))

        cursor.execute("""
            INSERT INTO booking (BookingID, TrackingNumber, CustomerID, FlightID, BookingDate)
            VALUES (%s, %s, %s, %s, NOW())
        """, (booking_id, tracking_number, customer_id, flight_id))

        cursor.execute("""
            UPDATE flight SET AvailableCapacity = AvailableCapacity - %s WHERE FlightID = %s
        """, (weight, flight_id))

        cursor.execute("""
            INSERT INTO trackinghistory (TrackingNumber, Status, Location, Remarks)
            VALUES (%s, 'Booked', %s, 'Cargo booked and awaiting flight')
        """, (tracking_number, source))

        conn.commit()
        print("\nBooking Successful!")
        print(f"Booking ID: {booking_id}")
        print(f"Tracking Number: {tracking_number} (Cost: ${total_cost})")

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"\nTransaction failed: {err}")

# ====================== EMPLOYEE FUNCTIONS ======================

def update_cargo_status(cursor, conn):
    print("\n===== Update Cargo Status =====")
    tracking_number = input("Enter Tracking Number: ").strip()

    try:
        cursor.execute("""
            SELECT CurrentStatus, Weight, b.FlightID, f.DestinationHub
            FROM cargo c
            JOIN booking b ON c.TrackingNumber = b.TrackingNumber
            JOIN flight f ON b.FlightID = f.FlightID
            WHERE c.TrackingNumber = %s
        """, (tracking_number,))
        result = cursor.fetchone()

        if not result:
            print("Cargo not found")
            return

        status, weight, flight_id, destination = result

        if status == 'Delivered':
            print("Cargo is already delivered")
            return

        confirm = input(f"Mark {tracking_number} as delivered to {destination}? (yes/no): ").lower()
        if confirm != 'yes':
            return

        cursor.execute("""
            UPDATE cargo SET CurrentStatus = 'Delivered', CurrentLocation = %s WHERE TrackingNumber = %s
        """, (destination, tracking_number))

        cursor.execute("""
            UPDATE flight SET AvailableCapacity = AvailableCapacity + %s WHERE FlightID = %s
        """, (weight, flight_id))

        cursor.execute("""
            INSERT INTO trackinghistory (TrackingNumber, Status, Location, Remarks)
            VALUES (%s, 'Delivered', %s, 'Package delivered successfully')
        """, (tracking_number, destination))

        conn.commit()
        print("\nCargo marked as delivered successfully!")

    except mysql.connector.Error as err:
        conn.rollback()
        print(f"\nUpdate failed: {err}")

def track_cargo(cursor):
    print("\n===== Track Cargo Status =====")
    tracking_number = input("Enter Tracking Number: ").strip()

    try:
        cursor.execute("""
            SELECT CurrentStatus, CurrentLocation FROM cargo WHERE TrackingNumber = %s
        """, (tracking_number,))
        cargo = cursor.fetchone()

        if not cargo:
            print("Cargo not found")
            return

        print(f"\nStatus: {cargo[0]}")
        print(f"Location: {cargo[1]}")

        print("\nTracking History:")
        cursor.execute("""
            SELECT Timestamp, Status, Location, Remarks 
            FROM trackinghistory WHERE TrackingNumber = %s ORDER BY Timestamp DESC
        """, (tracking_number,))
        
        for row in cursor.fetchall():
            print(f"[{row[0]}] {row[1]} at {row[2]} - {row[3]}")

    except mysql.connector.Error as err:
        print(f"\nTracking failed: {err}")

def check_flights(cursor):
    print("\n===== Check Flights Availability =====")
    
    cursor.execute("""
        SELECT FlightID, OriginHub, DestinationHub, DepartureDate, AvailableCapacity 
        FROM flight WHERE DepartureDate >= CURDATE() ORDER BY DepartureDate
    """)
    flights = cursor.fetchall()

    if not flights:
        print("\nNo flights found")
        return

    print("\nAvailable Flights:")
    for flight in flights:
        print(f"{flight[0]}: {flight[1]} -> {flight[2]} | Date: {flight[3]} | Capacity: {flight[4]}kg")

# ====================== MENUS ======================

def customer_menu(cursor, conn):
    while True:
        print("\n===== Customer Menu =====")
        print("1. Login")
        print("2. Register")
        print("3. Back")
        
        choice = input("Select option: ").strip()
        
        if choice == "1":
            customer_id = input("Enter Customer ID: ").strip()
            password = input("Enter Password: ").strip()
            
            cursor.execute("SELECT Name FROM customer WHERE CustomerID = %s AND PasswordHash = %s", (customer_id, password))
            customer = cursor.fetchone()
            
            if customer:
                print(f"\nWelcome back, {customer[0]}!")
                logged_in_menu(cursor, conn, customer_id)
            else:
                print("\nInvalid ID or Password.")
                
        elif choice == "2":
            customer_id = register_customer(cursor, conn)
            if customer_id:
                logged_in_menu(cursor, conn, customer_id)
        elif choice == "3":
            break

def logged_in_menu(cursor, conn, customer_id):
    while True:
        print(f"\n--- Customer Dashboard ({customer_id}) ---")
        print("1. Book Cargo")
        print("2. Update Address")
        print("3. Delete Account")
        print("4. Logout")
        
        choice = input("Select option: ").strip()
        
        if choice == "1":
            book_cargo(cursor, conn, customer_id)
        elif choice == "2":
            update_customer_address(cursor, conn)
        elif choice == "3":
            delete_customer(cursor, conn)
            break
        elif choice == "4":
            print("\nLogged out.")
            break

def employee_menu(cursor, conn):
    while True:
        print("\n===== Employee Menu =====")
        print("1. Update Cargo Status")
        print("2. Track Cargo")
        print("3. Check Flights")
        print("4. Back")
        
        choice = input("Select option: ").strip()
        
        if choice == "1":
            update_cargo_status(cursor, conn)
        elif choice == "2":
            track_cargo(cursor)
        elif choice == "3":
            check_flights(cursor)
        elif choice == "4":
            break

# ====================== MAIN ======================

def main():
    conn = connect()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        while True:
            print("\n===== Air-Travel Cargo Services =====")
            print("1. Customer")
            print("2. Employee")
            print("3. Exit")
            
            role = input("Select role: ").strip()
            
            if role == "1":
                customer_menu(cursor, conn)
            elif role == "2":
                employee_menu(cursor, conn)
            elif role == "3":
                print("\nThank you for using our services!")
                break
                
    except Exception as e:
        print(f"\nSystem error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()
