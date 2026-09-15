-- =================================================================================
-- Air-Travel Cargo Services - Exact Local Database Schema
-- Database: air_cargo
-- =================================================================================

CREATE DATABASE IF NOT EXISTS air_cargo;
USE air_cargo;

-- Drop tables if they exist to prevent conflicts during testing
DROP TABLE IF EXISTS trackinghistory;
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS cargo;
DROP TABLE IF EXISTS flight;
DROP TABLE IF EXISTS customer;

-- =================================================================================
-- 1. CREATE TABLES (Exact Match to Local Laptop Schema)
-- =================================================================================

CREATE TABLE `customer` (
  `CustomerID` varchar(20) NOT NULL,
  `Name` varchar(100) NOT NULL,
  `Email` varchar(100) NOT NULL,
  `Phone` varchar(10) NOT NULL,
  `Address` text NOT NULL,
  `PasswordHash` varchar(255) NOT NULL,
  PRIMARY KEY (`CustomerID`),
  UNIQUE KEY `Email` (`Email`),
  UNIQUE KEY `Phone` (`Phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `cargo` (
  `TrackingNumber` varchar(20) NOT NULL,
  `Weight` float NOT NULL,
  `CargoType` varchar(50) NOT NULL,
  `TotalCost` float NOT NULL,
  `CurrentStatus` varchar(50) NOT NULL,
  `CurrentLocation` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`TrackingNumber`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `flight` (
  `FlightID` varchar(20) NOT NULL,
  `OriginHub` varchar(100) NOT NULL,
  `DestinationHub` varchar(100) NOT NULL,
  `DepartureDate` date NOT NULL,
  `AvailableCapacity` float NOT NULL,
  PRIMARY KEY (`FlightID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `booking` (
  `BookingID` varchar(20) NOT NULL,
  `TrackingNumber` varchar(20) DEFAULT NULL,
  `CustomerID` varchar(20) DEFAULT NULL,
  `FlightID` varchar(20) DEFAULT NULL,
  `BookingDate` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`BookingID`),
  KEY `TrackingNumber` (`TrackingNumber`),
  KEY `CustomerID` (`CustomerID`),
  KEY `FlightID` (`FlightID`),
  CONSTRAINT `booking_ibfk_1` FOREIGN KEY (`TrackingNumber`) REFERENCES `cargo` (`TrackingNumber`) ON DELETE CASCADE,
  CONSTRAINT `booking_ibfk_2` FOREIGN KEY (`CustomerID`) REFERENCES `customer` (`CustomerID`) ON DELETE CASCADE,
  CONSTRAINT `booking_ibfk_3` FOREIGN KEY (`FlightID`) REFERENCES `flight` (`FlightID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `trackinghistory` (
  `UpdateID` int NOT NULL AUTO_INCREMENT,
  `TrackingNumber` varchar(20) NOT NULL,
  `Status` varchar(50) NOT NULL,
  `Location` varchar(100) NOT NULL,
  `Timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `Remarks` text,
  PRIMARY KEY (`UpdateID`),
  KEY `TrackingNumber` (`TrackingNumber`),
  CONSTRAINT `trackinghistory_ibfk_1` FOREIGN KEY (`TrackingNumber`) REFERENCES `cargo` (`TrackingNumber`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
