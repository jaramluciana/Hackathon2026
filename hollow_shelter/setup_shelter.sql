-- Run in a BACKED-UP TEST COPY of ResidentInfors. Does not drop existing tables.
-- Capacity defaults to zero: a coordinator must enter verified simulation capacities.
IF OBJECT_ID('dbo.Shelter_Capacity','U') IS NULL
CREATE TABLE dbo.Shelter_Capacity (
    [Level] INT NOT NULL PRIMARY KEY,
    Capacity INT NOT NULL DEFAULT 0 CHECK (Capacity >= 0),
    Occupied INT NOT NULL DEFAULT 0 CHECK (Occupied >= 0),
    CONSTRAINT CK_ShelterCapacity CHECK (Occupied <= Capacity)
);
IF OBJECT_ID('dbo.Shelter_Requests','U') IS NULL
CREATE TABLE dbo.Shelter_Requests (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    UserID NVARCHAR(50) NOT NULL,
    SourceLevel INT NOT NULL,
    PartySize INT NOT NULL CHECK (PartySize BETWEEN 1 AND 20),
    [Status] NVARCHAR(20) NOT NULL DEFAULT 'Pending'
      CHECK ([Status] IN ('Pending','Approved','Rejected','Cancelled')),
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
IF OBJECT_ID('dbo.Shelter_Assignments','U') IS NULL
CREATE TABLE dbo.Shelter_Assignments (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    RequestID INT NOT NULL UNIQUE REFERENCES dbo.Shelter_Requests(ID),
    UserID NVARCHAR(50) NOT NULL,
    SourceLevel INT NOT NULL,
    DestinationLevel INT NOT NULL,
    PartySize INT NOT NULL CHECK (PartySize BETWEEN 1 AND 20),
    [Status] NVARCHAR(20) NOT NULL CHECK ([Status] IN ('Pending','Approved','Arrived','Cancelled','Departed')),
    Instructions NVARCHAR(2000) NOT NULL,
    ApprovedBy NVARCHAR(50) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
-- Only register levels; do not invent safe available spaces.
INSERT INTO dbo.Shelter_Capacity ([Level], Capacity, Occupied)
SELECT l.[Level], 0, 0 FROM dbo.Levels l
WHERE NOT EXISTS (SELECT 1 FROM dbo.Shelter_Capacity s WHERE s.[Level]=l.[Level]);
-- Example for demo ONLY after verifying scenario: UPDATE dbo.Shelter_Capacity SET Capacity=200, Occupied=20 WHERE [Level]=5;
