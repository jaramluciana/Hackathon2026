-- Execute ONCE in your existing ResidentInfors SQL Server database.
-- Additive: no DROP, no changes to existing teammate tables.
IF OBJECT_ID('dbo.Med_Clinics','U') IS NULL
CREATE TABLE dbo.Med_Clinics(
 ClinicID INT IDENTITY(1,1) PRIMARY KEY, [Level] INT NOT NULL,
 Name NVARCHAR(120) NOT NULL, SlotsTotal INT NOT NULL CHECK(SlotsTotal>=0),
 SlotsUsed INT NOT NULL DEFAULT 0 CHECK(SlotsUsed>=0 AND SlotsUsed<=SlotsTotal));
IF OBJECT_ID('dbo.Med_Inventory','U') IS NULL
CREATE TABLE dbo.Med_Inventory(
 ClinicID INT NOT NULL REFERENCES dbo.Med_Clinics(ClinicID),
 Item NVARCHAR(60) NOT NULL, Quantity INT NOT NULL DEFAULT 0 CHECK(Quantity>=0),
 Reserve INT NOT NULL DEFAULT 0 CHECK(Reserve>=0), PRIMARY KEY(ClinicID,Item));
IF OBJECT_ID('dbo.Med_Requests','U') IS NULL
CREATE TABLE dbo.Med_Requests(
 RequestID INT IDENTITY(1,1) PRIMARY KEY, UserID NVARCHAR(50) NOT NULL,
 [Level] INT NOT NULL, Kind NVARCHAR(30) NOT NULL,
 Message NVARCHAR(1000) NOT NULL, Status NVARCHAR(30) NOT NULL DEFAULT 'pending',
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('dbo.Med_Appointments','U') IS NULL
CREATE TABLE dbo.Med_Appointments(
 AppointmentID INT IDENTITY(1,1) PRIMARY KEY, UserID NVARCHAR(50) NOT NULL,
 ClinicID INT NOT NULL REFERENCES dbo.Med_Clinics(ClinicID),
 Status NVARCHAR(30) NOT NULL DEFAULT 'requested',
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('dbo.Med_Notices','U') IS NULL
CREATE TABLE dbo.Med_Notices(
 NoticeID INT IDENTITY(1,1) PRIMARY KEY, [Level] INT NULL,
 Message NVARCHAR(1000) NOT NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('dbo.Med_Transfers','U') IS NULL
CREATE TABLE dbo.Med_Transfers(
 TransferID INT IDENTITY(1,1) PRIMARY KEY,
 SourceClinicID INT NOT NULL REFERENCES dbo.Med_Clinics(ClinicID),
 TargetClinicID INT NOT NULL REFERENCES dbo.Med_Clinics(ClinicID),
 Item NVARCHAR(60) NOT NULL, Quantity INT NOT NULL CHECK(Quantity>0),
 Status NVARCHAR(30) NOT NULL DEFAULT 'proposed',
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
-- Seed only when empty; adjust numbers for the fictional scenario.
IF NOT EXISTS (SELECT 1 FROM dbo.Med_Clinics)
BEGIN
 INSERT INTO dbo.Med_Clinics([Level],Name,SlotsTotal)
 VALUES (1,'Level 1 Clinic',35),(2,'Level 2 Clinic',35),(3,'Level 3 Clinic',35),
 (4,'Level 4 Clinic',35),(5,'Level 5 Clinic',35),(6,'Level 6 Clinic',35),
 (7,'Level 7 Clinic',35),(8,'Level 8 Medical Center',120),
 (9,'Level 9 Clinic',35),(10,'Level 10 Clinic',35);
END;
INSERT INTO dbo.Med_Inventory(ClinicID,Item,Quantity,Reserve)
SELECT c.ClinicID,v.Item,v.Qty,v.Reserve FROM dbo.Med_Clinics c
CROSS JOIN (VALUES ('medical_kits',100,25),('oxygen_tanks',60,15),('water_packs',150,30)) v(Item,Qty,Reserve)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Med_Inventory i WHERE i.ClinicID=c.ClinicID AND i.Item=v.Item);
