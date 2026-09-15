-- =================================================================================
-- Air-Travel Cargo Services - Seed Data (Dummy Rows)
-- Database: air_cargo
-- =================================================================================

USE air_cargo;

-- 1. Seed Upcoming Flights (Required for Book Cargo to work)
INSERT INTO `flight` (`FlightID`, `OriginHub`, `DestinationHub`, `DepartureDate`, `AvailableCapacity`) VALUES 
('FL-101', 'New York (JFK)', 'London (LHR)', DATE_ADD(CURDATE(), INTERVAL 2 DAY), 5000.0),
('FL-202', 'Singapore (SIN)', 'Frankfurt (FRA)', DATE_ADD(CURDATE(), INTERVAL 3 DAY), 10000.0),
('FL-303', 'London (LHR)', 'Dubai (DXB)', DATE_ADD(CURDATE(), INTERVAL 5 DAY), 7500.0),
('FL-404', 'Los Angeles (LAX)', 'Tokyo (NRT)', DATE_ADD(CURDATE(), INTERVAL 1 DAY), 2500.0),
('FL-505', 'Frankfurt (FRA)', 'New York (JFK)', DATE_ADD(CURDATE(), INTERVAL 4 DAY), 8000.0)
ON DUPLICATE KEY UPDATE `AvailableCapacity` = `AvailableCapacity`;

-- 2. Seed a dummy Customer with a basic plain-text password for testing
INSERT INTO `customer` (`CustomerID`, `Name`, `Email`, `Phone`, `Address`, `PasswordHash`) VALUES 
('CUST001', 'Acme Corp', 'shipping@acme.com', '1234567890', '123 Business Rd, New York', 'password123')
ON DUPLICATE KEY UPDATE `Name` = `Name`;
