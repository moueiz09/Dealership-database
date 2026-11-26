BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "Customer" (
	"CustomerID"	CHAR(9) NOT NULL,
	"Name"	VARCHAR(100) NOT NULL,
	PRIMARY KEY("CustomerID")
);
CREATE TABLE IF NOT EXISTS "Employee" (
	"EmployeeID"	INTEGER NOT NULL,
	"NAME"	VARCHAR(100) NOT NULL,
	"SSN"	CHAR(9) NOT NULL UNIQUE,
	"HiringDate"	DATE NOT NULL,
	PRIMARY KEY("EmployeeID")
);
CREATE TABLE IF NOT EXISTS "Manager" (
	"EmployeeID"	INTEGER NOT NULL,
	PRIMARY KEY("EmployeeID"),
	FOREIGN KEY("EmployeeID") REFERENCES "Employee"("EmployeeID")
);
CREATE TABLE IF NOT EXISTS "New_Vehicle" (
	"VIN"	VARCHAR(17) NOT NULL,
	"MSRP"	INTEGER NOT NULL,
	"ManufacturerSpecial"	VARCHAR(100) NOT NULL,
	PRIMARY KEY("VIN"),
	FOREIGN KEY("VIN") REFERENCES "Vehicle"("VIN")
);
CREATE TABLE IF NOT EXISTS "Salesperson" (
	"EmployeeID"	INTEGER NOT NULL,
	"ManagerID"	INTEGER NOT NULL,
	"SalesMetrics"	INTEGER NOT NULL,
	PRIMARY KEY("EmployeeID"),
	FOREIGN KEY("EmployeeID") REFERENCES "Employee"("EmployeeID"),
	FOREIGN KEY("ManagerID") REFERENCES "Manager"("EmployeeID")
);
CREATE TABLE IF NOT EXISTS "Transaction" (
	"TransactionID"	INTEGER NOT NULL,
	"Amount"	INTEGER NOT NULL,
	"VIN"	VARCHAR(17) NOT NULL UNIQUE,
	"CustomerID"	Char(9) NOT NULL,
	"SalespersonID"	INTEGER NOT NULL,
	"SalesDate"	DATE NOT NULL,
	PRIMARY KEY("TransactionID"),
	FOREIGN KEY("CustomerID") REFERENCES "Customer"("CustomerID"),
	FOREIGN KEY("SalespersonID") REFERENCES "Salesperson"("EmployeeID"),
	FOREIGN KEY("VIN") REFERENCES "Vehicle"("VIN")
);
CREATE TABLE IF NOT EXISTS "Used_Vehicle" (
	"VIN"	VARCHAR(17) NOT NULL,
	"Mileage"	INTEGER NOT NULL,
	"FactoryWarranty"	VARCHAR(100),
	"TotalMoneySpent"	INTEGER NOT NULL,
	PRIMARY KEY("VIN"),
	FOREIGN KEY("VIN") REFERENCES "Vehicle"("VIN")
);
CREATE TABLE IF NOT EXISTS "Vehicle" (
	"VIN"	VARCHAR(17) NOT NULL,
	"Make"	VARCHAR(40) NOT NULL,
	"Model"	VARCHAR(40) NOT NULL,
	"VehicleYear"	INTEGER NOT NULL,
	"Status"	VARCHAR(40) NOT NULL CHECK("Status" IN ('Available', 'Pending', 'Sold')),
	"Color"	VARCHAR(40) NOT NULL,
	PRIMARY KEY("VIN")
);
COMMIT;
