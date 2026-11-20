-- Run in the same SQL Server database used by database.py (e.g. ResidentInfors).
-- Additive and rerunnable; does not drop existing tables or data.
IF OBJECT_ID('dbo.Connect_Teams','U') IS NULL
CREATE TABLE dbo.Connect_Teams (
 ID INT IDENTITY(1,1) PRIMARY KEY,
 TeamName NVARCHAR(100) NOT NULL,
 TeamType NVARCHAR(40) NOT NULL,
 [Level] INT NOT NULL CHECK ([Level] BETWEEN 1 AND 10),
 [Status] NVARCHAR(20) NOT NULL DEFAULT 'Available',
 Capacity INT NOT NULL DEFAULT 1 CHECK (Capacity > 0)
);
IF OBJECT_ID('dbo.Connect_Reports','U') IS NULL
CREATE TABLE dbo.Connect_Reports (
 ID INT IDENTITY(1,1) PRIMARY KEY,
 ReporterID NVARCHAR(50) NOT NULL,
 [Level] INT NOT NULL CHECK ([Level] BETWEEN 1 AND 10),
 Category NVARCHAR(40) NOT NULL,
 Urgency NVARCHAR(20) NOT NULL,
 [Description] NVARCHAR(1500) NOT NULL,
 [Status] NVARCHAR(25) NOT NULL DEFAULT 'Submitted',
 AssignedTeamID INT NULL REFERENCES dbo.Connect_Teams(ID),
 CoordinatorNote NVARCHAR(1000) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
 UpdatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
IF OBJECT_ID('dbo.Connect_History','U') IS NULL
CREATE TABLE dbo.Connect_History (
 ID INT IDENTITY(1,1) PRIMARY KEY,
 ReportID INT NOT NULL REFERENCES dbo.Connect_Reports(ID),
 ActorID NVARCHAR(50) NOT NULL,
 Action NVARCHAR(30) NOT NULL,
 Note NVARCHAR(1000) NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
IF OBJECT_ID('dbo.Connect_Announcements','U') IS NULL
CREATE TABLE dbo.Connect_Announcements (
 ID INT IDENTITY(1,1) PRIMARY KEY,
 [Level] INT NULL CHECK ([Level] BETWEEN 1 AND 10),
 Title NVARCHAR(120) NOT NULL,
 Body NVARCHAR(2000) NOT NULL,
 AuthorID NVARCHAR(50) NOT NULL,
 CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
-- Demo teams, inserted only when table is empty.
IF NOT EXISTS (SELECT 1 FROM dbo.Connect_Teams)
INSERT INTO dbo.Connect_Teams (TeamName,TeamType,[Level],Capacity) VALUES
('Medic Alpha','Medical',2,2),('Medic Beta','Medical',7,2),
('Rescue One','Rescue',3,3),('Rescue Two','Rescue',8,3),
('Engineering One','Engineering',5,2),('Security One','Security',6,2),
('Supply One','Resource Support',4,2);
