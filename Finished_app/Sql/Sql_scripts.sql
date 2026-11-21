Create database ResidentInfors;
Go


USE [ResidentInfors]
GO
/****** Object:  Table [dbo].[Account]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Account](
	[UserID] [nvarchar](50) NOT NULL,
	[Password] [nvarchar](255) NOT NULL,
	[Level] [int] NOT NULL,
	[FirstName] [nvarchar](50) NULL,
	[LastName] [nvarchar](50) NULL,
	[DateOfBirth] [date] NULL,
	[ResidentID] [int] NULL,
PRIMARY KEY CLUSTERED 
(
	[UserID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Event_Log]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Event_Log](
	[ID] [bigint] IDENTITY(1,1) NOT NULL,
	[Sim_Time] [float] NOT NULL,
	[Level] [int] NULL,
	[System] [nvarchar](50) NULL,
	[Message] [nvarchar](400) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Applications]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Explore_Applications](
	[ApplicationID] [int] IDENTITY(1,1) NOT NULL,
	[MissionID] [int] NOT NULL,
	[ResidentID] [int] NOT NULL,
	[Status] [nvarchar](12) NOT NULL,
	[AppliedAt] [datetime2](7) NOT NULL,
	[CompletedAt] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[ApplicationID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Explore_App] UNIQUE NONCLUSTERED 
(
	[MissionID] ASC,
	[ResidentID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Missions]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Explore_Missions](
	[MissionID] [int] IDENTITY(1,1) NOT NULL,
	[Title] [nvarchar](150) NOT NULL,
	[SectorCode] [nvarchar](8) NOT NULL,
	[Kind] [nvarchar](30) NOT NULL,
	[DurationHours] [float] NOT NULL,
	[BaseReward] [int] NOT NULL,
	[MaxHazard] [int] NOT NULL,
	[PreferredJobs] [nvarchar](200) NOT NULL,
	[Objective] [nvarchar](300) NOT NULL,
	[Status] [nvarchar](10) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[MissionID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Reports]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Explore_Reports](
	[ReportID] [int] IDENTITY(1,1) NOT NULL,
	[ApplicationID] [int] NOT NULL,
	[Findings] [nvarchar](2000) NOT NULL,
	[ResourceFound] [nvarchar](20) NOT NULL,
	[Verified] [smallint] NOT NULL,
	[SubmittedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ReportID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[ApplicationID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Rewards]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Explore_Rewards](
	[RewardID] [int] IDENTITY(1,1) NOT NULL,
	[ApplicationID] [int] NOT NULL,
	[ResidentID] [int] NOT NULL,
	[Amount] [int] NOT NULL,
	[PaidAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[RewardID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[ApplicationID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Sectors]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Explore_Sectors](
	[Code] [nvarchar](8) NOT NULL,
	[Name] [nvarchar](100) NOT NULL,
	[X] [float] NOT NULL,
	[Y] [float] NOT NULL,
	[Status] [nvarchar](20) NOT NULL,
	[Hazard] [int] NOT NULL,
	[Resource] [nvarchar](20) NOT NULL,
	[Confidence] [float] NOT NULL,
	[Notes] [nvarchar](300) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[Code] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Effects]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Level_Effects](
	[Level] [int] NOT NULL,
	[Rate_Health] [float] NOT NULL,
	[Pending_Health] [float] NOT NULL,
	[Rate_Money] [float] NOT NULL,
	[Pending_Money] [float] NOT NULL,
	[Rate_Heal] [float] NOT NULL,
	[Pending_Heal] [float] NOT NULL,
	[Rate_Cure] [float] NOT NULL,
	[Pending_Cure] [float] NOT NULL,
	[Healed_To] [float] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[Level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Supply]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Level_Supply](
	[Level] [int] NOT NULL,
	[System] [nvarchar](50) NOT NULL,
	[Capacity] [float] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[Level] ASC,
	[System] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Systems]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Level_Systems](
	[Level] [int] NOT NULL,
	[System] [nvarchar](50) NOT NULL,
	[Status] [float] NOT NULL,
 CONSTRAINT [PK_Level_Systems] PRIMARY KEY CLUSTERED 
(
	[Level] ASC,
	[System] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Levels]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Levels](
	[Level] [int] NOT NULL,
	[Name] [nvarchar](50) NULL,
	[Population] [int] NOT NULL,
	[Alive] [int] NOT NULL,
	[Engineers] [int] NOT NULL,
	[Farmers] [int] NOT NULL,
	[Medics] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[Level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Appointments]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Appointments](
	[AppointmentID] [int] IDENTITY(1,1) NOT NULL,
	[UserID] [nvarchar](50) NOT NULL,
	[ClinicID] [int] NOT NULL,
	[Status] [nvarchar](30) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[AppointmentID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Clinics]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Clinics](
	[ClinicID] [int] IDENTITY(1,1) NOT NULL,
	[Level] [int] NOT NULL,
	[Name] [nvarchar](120) NOT NULL,
	[SlotsTotal] [int] NOT NULL,
	[SlotsUsed] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ClinicID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Inventory]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Inventory](
	[ClinicID] [int] NOT NULL,
	[Item] [nvarchar](60) NOT NULL,
	[Quantity] [int] NOT NULL,
	[Reserve] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ClinicID] ASC,
	[Item] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Notices]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Notices](
	[NoticeID] [int] IDENTITY(1,1) NOT NULL,
	[Level] [int] NULL,
	[Message] [nvarchar](1000) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[NoticeID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Requests]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Requests](
	[RequestID] [int] IDENTITY(1,1) NOT NULL,
	[UserID] [nvarchar](50) NOT NULL,
	[Level] [int] NOT NULL,
	[Kind] [nvarchar](30) NOT NULL,
	[Message] [nvarchar](1000) NOT NULL,
	[Status] [nvarchar](30) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[RequestID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Transfers]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Transfers](
	[TransferID] [int] IDENTITY(1,1) NOT NULL,
	[SourceClinicID] [int] NOT NULL,
	[TargetClinicID] [int] NOT NULL,
	[Item] [nvarchar](60) NOT NULL,
	[Quantity] [int] NOT NULL,
	[Status] [nvarchar](30) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[TransferID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Residents]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Residents](
	[ID] [int] NOT NULL,
	[Work] [nvarchar](30) NOT NULL,
	[Health] [int] NOT NULL,
	[Family] [int] NOT NULL,
	[Level] [int] NOT NULL,
	[Money] [int] NOT NULL,
	[LungDisease] [bit] NOT NULL,
	[Moving] [bit] NOT NULL,
	[AwayFrom] [int] NULL,
	[LiveStatus]  AS (CONVERT([varchar](10),case when [Health]>(0) then 'alive' else 'dead' end)),
	[Salary] [int] NULL,
	[Important] [bit] NULL,
PRIMARY KEY CLUSTERED 
(
	[ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Shelter_Assignments]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Shelter_Assignments](
	[ID] [int] IDENTITY(1,1) NOT NULL,
	[RequestID] [int] NOT NULL,
	[UserID] [nvarchar](50) NOT NULL,
	[SourceLevel] [int] NOT NULL,
	[DestinationLevel] [int] NOT NULL,
	[PartySize] [int] NOT NULL,
	[Status] [nvarchar](20) NOT NULL,
	[Instructions] [nvarchar](2000) NOT NULL,
	[ApprovedBy] [nvarchar](50) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[RequestID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Shelter_Capacity]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Shelter_Capacity](
	[Level] [int] NOT NULL,
	[Capacity] [int] NOT NULL,
	[Occupied] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[Level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Shelter_Requests]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Shelter_Requests](
	[ID] [int] IDENTITY(1,1) NOT NULL,
	[UserID] [nvarchar](50) NOT NULL,
	[SourceLevel] [int] NOT NULL,
	[PartySize] [int] NOT NULL,
	[Status] [nvarchar](20) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[ID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[System_Types]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[System_Types](
	[System] [nvarchar](50) NOT NULL,
	[Group] [nvarchar](100) NOT NULL,
	[Effect_Stat] [nvarchar](10) NOT NULL,
	[Max_Rate] [float] NOT NULL,
	[Threshold] [float] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[System] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Index [IX_EventLog_SimTime]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_EventLog_SimTime] ON [dbo].[Event_Log]
(
	[Sim_Time] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Med_Appointments_User]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Med_Appointments_User] ON [dbo].[Med_Appointments]
(
	[UserID] ASC,
	[AppointmentID] DESC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Object:  Index [IX_Med_Notices_Level]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Med_Notices_Level] ON [dbo].[Med_Notices]
(
	[Level] ASC,
	[NoticeID] DESC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Med_Requests_User]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Med_Requests_User] ON [dbo].[Med_Requests]
(
	[UserID] ASC,
	[RequestID] DESC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Object:  Index [IX_Residents_Away]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Away] ON [dbo].[Residents]
(
	[AwayFrom] ASC
)
WHERE ([AwayFrom] IS NOT NULL)
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Residents_Dead]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Dead] ON [dbo].[Residents]
(
	[Level] ASC,
	[Work] ASC
)
WHERE ([Health]=(0))
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Object:  Index [IX_Residents_Level]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Level] ON [dbo].[Residents]
(
	[Level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Residents_Moving]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Moving] ON [dbo].[Residents]
(
	[Level] ASC,
	[Work] ASC
)
WHERE ([Moving]=(1))
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Object:  Index [IX_Residents_Sick]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Sick] ON [dbo].[Residents]
(
	[Level] ASC
)
WHERE ([LungDisease]=(1))
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Residents_Work]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Work] ON [dbo].[Residents]
(
	[Work] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Object:  Index [IX_Residents_Work_Level]    Script Date: 20/11/2026 8:56:46 CH ******/
CREATE NONCLUSTERED INDEX [IX_Residents_Work_Level] ON [dbo].[Residents]
(
	[Work] ASC,
	[Level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
ALTER TABLE [dbo].[Account] ADD  CONSTRAINT [DF_Account_Level]  DEFAULT ((1)) FOR [Level]
GO
ALTER TABLE [dbo].[Explore_Applications] ADD  DEFAULT ('pending') FOR [Status]
GO
ALTER TABLE [dbo].[Explore_Applications] ADD  DEFAULT (sysdatetime()) FOR [AppliedAt]
GO
ALTER TABLE [dbo].[Explore_Missions] ADD  DEFAULT ('open') FOR [Status]
GO
ALTER TABLE [dbo].[Explore_Reports] ADD  DEFAULT ((0)) FOR [Verified]
GO
ALTER TABLE [dbo].[Explore_Reports] ADD  DEFAULT (sysdatetime()) FOR [SubmittedAt]
GO
ALTER TABLE [dbo].[Explore_Rewards] ADD  DEFAULT (sysdatetime()) FOR [PaidAt]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LevelEffects_RateHealth]  DEFAULT ((0)) FOR [Rate_Health]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LevelEffects_PendingHealth]  DEFAULT ((0)) FOR [Pending_Health]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LevelEffects_RateMoney]  DEFAULT ((0)) FOR [Rate_Money]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LevelEffects_PendingMoney]  DEFAULT ((0)) FOR [Pending_Money]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LE_RateHeal]  DEFAULT ((0)) FOR [Rate_Heal]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LE_PendHeal]  DEFAULT ((0)) FOR [Pending_Heal]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LE_RateCure]  DEFAULT ((0)) FOR [Rate_Cure]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LE_PendCure]  DEFAULT ((0)) FOR [Pending_Cure]
GO
ALTER TABLE [dbo].[Level_Effects] ADD  CONSTRAINT [DF_LE_HealedTo]  DEFAULT ((0)) FOR [Healed_To]
GO
ALTER TABLE [dbo].[Level_Systems] ADD  CONSTRAINT [DF_LevelSystems_Status]  DEFAULT ((100)) FOR [Status]
GO
ALTER TABLE [dbo].[Levels] ADD  CONSTRAINT [DF_Levels_Population]  DEFAULT ((0)) FOR [Population]
GO
ALTER TABLE [dbo].[Levels] ADD  CONSTRAINT [DF_Levels_Alive]  DEFAULT ((0)) FOR [Alive]
GO
ALTER TABLE [dbo].[Levels] ADD  CONSTRAINT [DF_Levels_Engineers]  DEFAULT ((0)) FOR [Engineers]
GO
ALTER TABLE [dbo].[Levels] ADD  CONSTRAINT [DF_Levels_Farmers]  DEFAULT ((0)) FOR [Farmers]
GO
ALTER TABLE [dbo].[Levels] ADD  CONSTRAINT [DF_Levels_Medics]  DEFAULT ((0)) FOR [Medics]
GO
ALTER TABLE [dbo].[Med_Appointments] ADD  DEFAULT ('requested') FOR [Status]
GO
ALTER TABLE [dbo].[Med_Appointments] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Med_Clinics] ADD  DEFAULT ((0)) FOR [SlotsUsed]
GO
ALTER TABLE [dbo].[Med_Inventory] ADD  DEFAULT ((0)) FOR [Quantity]
GO
ALTER TABLE [dbo].[Med_Inventory] ADD  DEFAULT ((0)) FOR [Reserve]
GO
ALTER TABLE [dbo].[Med_Notices] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Med_Requests] ADD  DEFAULT ('pending') FOR [Status]
GO
ALTER TABLE [dbo].[Med_Requests] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Med_Transfers] ADD  DEFAULT ('proposed') FOR [Status]
GO
ALTER TABLE [dbo].[Med_Transfers] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Residents] ADD  CONSTRAINT [DF_Residents_LungDisease]  DEFAULT ((0)) FOR [LungDisease]
GO
ALTER TABLE [dbo].[Residents] ADD  CONSTRAINT [DF_Residents_Moving]  DEFAULT ((0)) FOR [Moving]
GO
ALTER TABLE [dbo].[Shelter_Assignments] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Shelter_Capacity] ADD  DEFAULT ((0)) FOR [Capacity]
GO
ALTER TABLE [dbo].[Shelter_Capacity] ADD  DEFAULT ((0)) FOR [Occupied]
GO
ALTER TABLE [dbo].[Shelter_Requests] ADD  DEFAULT ('Pending') FOR [Status]
GO
ALTER TABLE [dbo].[Shelter_Requests] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[System_Types] ADD  CONSTRAINT [DF_SystemTypes_Threshold]  DEFAULT ((100)) FOR [Threshold]
GO
ALTER TABLE [dbo].[Explore_Applications]  WITH CHECK ADD FOREIGN KEY([MissionID])
REFERENCES [dbo].[Explore_Missions] ([MissionID])
GO
ALTER TABLE [dbo].[Explore_Missions]  WITH CHECK ADD FOREIGN KEY([SectorCode])
REFERENCES [dbo].[Explore_Sectors] ([Code])
GO
ALTER TABLE [dbo].[Explore_Reports]  WITH CHECK ADD FOREIGN KEY([ApplicationID])
REFERENCES [dbo].[Explore_Applications] ([ApplicationID])
GO
ALTER TABLE [dbo].[Explore_Rewards]  WITH CHECK ADD FOREIGN KEY([ApplicationID])
REFERENCES [dbo].[Explore_Applications] ([ApplicationID])
GO
ALTER TABLE [dbo].[Level_Effects]  WITH CHECK ADD  CONSTRAINT [FK_LevelEffects_Levels] FOREIGN KEY([Level])
REFERENCES [dbo].[Levels] ([Level])
GO
ALTER TABLE [dbo].[Level_Effects] CHECK CONSTRAINT [FK_LevelEffects_Levels]
GO
ALTER TABLE [dbo].[Level_Supply]  WITH CHECK ADD FOREIGN KEY([Level])
REFERENCES [dbo].[Levels] ([Level])
GO
ALTER TABLE [dbo].[Level_Supply]  WITH CHECK ADD FOREIGN KEY([System])
REFERENCES [dbo].[System_Types] ([System])
GO
ALTER TABLE [dbo].[Level_Systems]  WITH CHECK ADD  CONSTRAINT [FK_LevelSystems_Levels] FOREIGN KEY([Level])
REFERENCES [dbo].[Levels] ([Level])
GO
ALTER TABLE [dbo].[Level_Systems] CHECK CONSTRAINT [FK_LevelSystems_Levels]
GO
ALTER TABLE [dbo].[Level_Systems]  WITH CHECK ADD  CONSTRAINT [FK_LevelSystems_SystemTypes] FOREIGN KEY([System])
REFERENCES [dbo].[System_Types] ([System])
GO
ALTER TABLE [dbo].[Level_Systems] CHECK CONSTRAINT [FK_LevelSystems_SystemTypes]
GO
ALTER TABLE [dbo].[Med_Appointments]  WITH CHECK ADD FOREIGN KEY([ClinicID])
REFERENCES [dbo].[Med_Clinics] ([ClinicID])
GO
ALTER TABLE [dbo].[Med_Inventory]  WITH CHECK ADD FOREIGN KEY([ClinicID])
REFERENCES [dbo].[Med_Clinics] ([ClinicID])
GO
ALTER TABLE [dbo].[Med_Transfers]  WITH CHECK ADD FOREIGN KEY([SourceClinicID])
REFERENCES [dbo].[Med_Clinics] ([ClinicID])
GO
ALTER TABLE [dbo].[Med_Transfers]  WITH CHECK ADD FOREIGN KEY([TargetClinicID])
REFERENCES [dbo].[Med_Clinics] ([ClinicID])
GO
ALTER TABLE [dbo].[Residents]  WITH CHECK ADD  CONSTRAINT [FK_Residents_AwayFrom] FOREIGN KEY([AwayFrom])
REFERENCES [dbo].[Levels] ([Level])
GO
ALTER TABLE [dbo].[Residents] CHECK CONSTRAINT [FK_Residents_AwayFrom]
GO
ALTER TABLE [dbo].[Residents]  WITH CHECK ADD  CONSTRAINT [FK_Residents_Levels] FOREIGN KEY([Level])
REFERENCES [dbo].[Levels] ([Level])
GO
ALTER TABLE [dbo].[Residents] CHECK CONSTRAINT [FK_Residents_Levels]
GO
ALTER TABLE [dbo].[Shelter_Assignments]  WITH CHECK ADD FOREIGN KEY([RequestID])
REFERENCES [dbo].[Shelter_Requests] ([ID])
GO
ALTER TABLE [dbo].[Account]  WITH CHECK ADD  CONSTRAINT [CK_Account_Level] CHECK  (([Level]>=(1) AND [Level]<=(10)))
GO
ALTER TABLE [dbo].[Account] CHECK CONSTRAINT [CK_Account_Level]
GO
ALTER TABLE [dbo].[Explore_Applications]  WITH CHECK ADD CHECK  (([Status]='cancelled' OR [Status]='completed' OR [Status]='active' OR [Status]='rejected' OR [Status]='approved' OR [Status]='pending'))
GO
ALTER TABLE [dbo].[Explore_Missions]  WITH CHECK ADD CHECK  (([Status]='closed' OR [Status]='paused' OR [Status]='open'))
GO
ALTER TABLE [dbo].[Explore_Rewards]  WITH CHECK ADD CHECK  (([Amount]>=(0)))
GO
ALTER TABLE [dbo].[Explore_Sectors]  WITH CHECK ADD CHECK  (([Confidence]>=(0) AND [Confidence]<=(1)))
GO
ALTER TABLE [dbo].[Explore_Sectors]  WITH CHECK ADD CHECK  (([Hazard]>=(0) AND [Hazard]<=(100)))
GO
ALTER TABLE [dbo].[Level_Systems]  WITH CHECK ADD CHECK  (([Status]>=(0) AND [Status]<=(100)))
GO
ALTER TABLE [dbo].[Levels]  WITH CHECK ADD CHECK  (([Level]>=(1)))
GO
ALTER TABLE [dbo].[Med_Clinics]  WITH CHECK ADD CHECK  (([SlotsTotal]>=(0)))
GO
ALTER TABLE [dbo].[Med_Clinics]  WITH CHECK ADD  CONSTRAINT [CK_Med_Clinics_Slots] CHECK  (([SlotsUsed]>=(0) AND [SlotsUsed]<=[SlotsTotal]))
GO
ALTER TABLE [dbo].[Med_Clinics] CHECK CONSTRAINT [CK_Med_Clinics_Slots]
GO
ALTER TABLE [dbo].[Med_Inventory]  WITH CHECK ADD CHECK  (([Quantity]>=(0)))
GO
ALTER TABLE [dbo].[Med_Inventory]  WITH CHECK ADD CHECK  (([Reserve]>=(0)))
GO
ALTER TABLE [dbo].[Med_Transfers]  WITH CHECK ADD CHECK  (([Quantity]>(0)))
GO
ALTER TABLE [dbo].[Residents]  WITH CHECK ADD CHECK  (([Family]>=(0)))
GO
ALTER TABLE [dbo].[Residents]  WITH CHECK ADD CHECK  (([Health]>=(0) AND [Health]<=(100)))
GO
ALTER TABLE [dbo].[Shelter_Assignments]  WITH CHECK ADD CHECK  (([PartySize]>=(1) AND [PartySize]<=(20)))
GO
ALTER TABLE [dbo].[Shelter_Assignments]  WITH CHECK ADD CHECK  (([Status]='Departed' OR [Status]='Cancelled' OR [Status]='Arrived' OR [Status]='Approved' OR [Status]='Pending'))
GO
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD CHECK  (([Capacity]>=(0)))
GO
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD CHECK  (([Occupied]>=(0)))
GO
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD  CONSTRAINT [CK_ShelterCapacity] CHECK  (([Occupied]<=[Capacity]))
GO
ALTER TABLE [dbo].[Shelter_Capacity] CHECK CONSTRAINT [CK_ShelterCapacity]
GO
ALTER TABLE [dbo].[Shelter_Requests]  WITH CHECK ADD CHECK  (([PartySize]>=(1) AND [PartySize]<=(20)))
GO
ALTER TABLE [dbo].[Shelter_Requests]  WITH CHECK ADD CHECK  (([Status]='Cancelled' OR [Status]='Rejected' OR [Status]='Approved' OR [Status]='Pending'))
GO
ALTER TABLE [dbo].[System_Types]  WITH CHECK ADD CHECK  (([Effect_Stat]=N'money' OR [Effect_Stat]=N'health'))
GO
ALTER TABLE [dbo].[System_Types]  WITH CHECK ADD  CONSTRAINT [CK_SystemTypes_Threshold] CHECK  (([Threshold]>(0) AND [Threshold]<=(100)))
GO
ALTER TABLE [dbo].[System_Types] CHECK CONSTRAINT [CK_SystemTypes_Threshold]
GO
/****** Object:  StoredProcedure [dbo].[usp_AllocateSupplies]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[usp_AllocateSupplies]
AS
BEGIN
    SET NOCOUNT ON;
    -- Split ONE stockpile of food and medicine between the levels: weights fall in a straight
    -- line from 2.0 (top) to 1.0, the bottom 20% of levels get 0.3. Call after usp_RefreshPopulation.
    DECLARE @n INT = (SELECT COUNT(*) FROM dbo.Levels);
    DECLARE @nshort INT = CAST(ROUND(@n * 0.2, 0) AS INT);
    DECLARE @nok INT = @n - @nshort;
    DECLARE @hours FLOAT = 120.0;      -- sim-hours of consumption for the average resident

    CREATE TABLE #W ([Level] INT, Pop FLOAT, W FLOAT);
    INSERT INTO #W
    SELECT [Level], CAST(Population AS FLOAT),
           CASE WHEN rn - 1 >= @nok THEN 0.3
                WHEN @nok <= 1 THEN 2.0
                ELSE 2.0 + (1.0 - 2.0) * (rn - 1) / (@nok - 1.0) END
    FROM (SELECT [Level], Population, ROW_NUMBER() OVER (ORDER BY [Level]) AS rn FROM dbo.Levels) AS x;

    DECLARE @totalPop FLOAT = (SELECT SUM(Pop) FROM #W);
    DECLARE @weighted FLOAT = (SELECT SUM(W * Pop) FROM #W);
    IF @weighted IS NULL OR @weighted = 0
    BEGIN
        DROP TABLE #W;
        RETURN;
    END;

    DELETE FROM dbo.Level_Supply;
    INSERT INTO dbo.Level_Supply ([Level], System, Capacity)
    SELECT w.[Level], s.System, @hours * 1.0 * @totalPop * w.W * w.Pop / @weighted
    FROM #W AS w CROSS JOIN (VALUES (N'food'), (N'medicine')) AS s(System);

    DROP TABLE #W;
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_CreateAccount]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[usp_CreateAccount]
    @FirstName   NVARCHAR(100),
    @LastName    NVARCHAR(100),
    @DateOfBirth DATE,
    @Level       INT,
    @Password    NVARCHAR(100),
    @Work        NVARCHAR(50),
    @Important   BIT = NULL,              -- NULL = decided by occupation
    @NewUserID   NVARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Level NOT BETWEEN 1 AND 10
        THROW 50001, 'Level must be between 1 and 10', 1;

    BEGIN TRAN;

    -- ID = letter of the level (A..J) + 7 digits, e.g. A0000001
    DECLARE @letter CHAR(1) = CHAR(64 + @Level);
    DECLARE @n INT;
    SELECT @n = ISNULL(MAX(TRY_CAST(SUBSTRING(UserID, 2, 10) AS INT)), 0) + 1
    FROM dbo.Account WITH (UPDLOCK, HOLDLOCK)
    WHERE UserID LIKE @letter + '[0-9]%';
    SET @NewUserID = @letter + RIGHT('0000000' + CAST(@n AS VARCHAR(10)), 7);

    DECLARE @imp BIT = ISNULL(@Important,
        CASE WHEN @Work IN ('medic', 'farmer', 'engineer') THEN 1 ELSE 0 END);

    -- new resident row
    DECLARE @rid INT;
    IF COLUMNPROPERTY(OBJECT_ID('dbo.Residents'), 'ID', 'IsIdentity') = 1
    BEGIN
        INSERT dbo.Residents (Work, Health, Family, [Level], Money, LungDisease, Moving, AwayFrom, Important)
        VALUES (@Work, 100, 1, @Level, 1000, 0, 0, NULL, @imp);
        SET @rid = CAST(SCOPE_IDENTITY() AS INT);
    END
    ELSE
    BEGIN
        SELECT @rid = ISNULL(MAX(ID), 0) + 1 FROM dbo.Residents WITH (UPDLOCK, HOLDLOCK);
        INSERT dbo.Residents (ID, Work, Health, Family, [Level], Money, LungDisease, Moving, AwayFrom, Important)
        VALUES (@rid, @Work, 100, 1, @Level, 1000, 0, 0, NULL, @imp);
    END

    INSERT dbo.Account (UserID, Password, [Level], FirstName, LastName, DateOfBirth, ResidentID)
    VALUES (@NewUserID, @Password, @Level, @FirstName, @LastName, @DateOfBirth, @rid);

    COMMIT;
END
GO
/****** Object:  StoredProcedure [dbo].[usp_DamageSystem]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE PROCEDURE [dbo].[usp_DamageSystem]
    @Level INT,
    @System NVARCHAR(50),
    @Amount FLOAT,
    @SimTime FLOAT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentStatus FLOAT;

    SELECT @CurrentStatus = [Status]
    FROM dbo.Level_Systems
    WHERE [Level] = @Level AND System = @System;

    IF @CurrentStatus IS NULL
        THROW 50002, 'System does not exist on the specified level.', 1;

    -- Positive amount damages; negative amount repairs.
DECLARE @NewStatus FLOAT;

SET @NewStatus = @CurrentStatus - @Amount;

EXEC dbo.usp_SetSystemStatus
    @Level = @Level,
    @System = @System,
    @Status = @NewStatus,
    @SimTime = @SimTime,
    @WriteLog = 1;
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_FlushEffects]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

/*==============================================================
  9. APPLY ACCUMULATED EFFECTS TO RESIDENTS
==============================================================*/
CREATE PROCEDURE [dbo].[usp_FlushEffects]
    @Level INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @Applied TABLE (
        [Level] INT PRIMARY KEY,
        HealthPointsApplied INT,
        MoneyApplied INT
    );

    BEGIN TRANSACTION;

    DECLARE @CurrentLevel INT;
    DECLARE @PendingHealth FLOAT;
    DECLARE @PendingMoney FLOAT;
    DECLARE @DamageHealth INT;
    DECLARE @DamageMoney INT;

    DECLARE effect_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT [Level], Pending_Health, Pending_Money
        FROM dbo.Level_Effects
        WHERE @Level IS NULL OR [Level] = @Level
        ORDER BY [Level];

    OPEN effect_cursor;

    FETCH NEXT FROM effect_cursor
    INTO @CurrentLevel, @PendingHealth, @PendingMoney;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @DamageHealth = FLOOR(@PendingHealth + 0.000000001);
        SET @DamageMoney = FLOOR(@PendingMoney + 0.000000001);

        IF @DamageHealth > 0 OR @DamageMoney > 0
        BEGIN
            -- As in the Python implementation, only living residents are updated.
            UPDATE dbo.Residents
            SET
                Health = CASE
                    WHEN Health - @DamageHealth < 0 THEN 0
                    ELSE Health - @DamageHealth
                END,
                Money = CASE
                    WHEN Money - @DamageMoney < 0 THEN 0
                    ELSE Money - @DamageMoney
                END
            WHERE [Level] = @CurrentLevel
              AND Health > 0;

            UPDATE dbo.Level_Effects
            SET
                Pending_Health = Pending_Health - @DamageHealth,
                Pending_Money = Pending_Money - @DamageMoney
            WHERE [Level] = @CurrentLevel;

            INSERT INTO @Applied ([Level], HealthPointsApplied, MoneyApplied)
            VALUES (@CurrentLevel, @DamageHealth, @DamageMoney);
        END;

        FETCH NEXT FROM effect_cursor
        INTO @CurrentLevel, @PendingHealth, @PendingMoney;
    END;

    CLOSE effect_cursor;
    DEALLOCATE effect_cursor;

    COMMIT TRANSACTION;

    SELECT [Level], HealthPointsApplied, MoneyApplied
    FROM @Applied
    ORDER BY [Level];
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_LevelDashboard]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

/*==============================================================
  11. REPORTING PROCEDURES
==============================================================*/
CREATE PROCEDURE [dbo].[usp_LevelDashboard]
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        l.[Level],
        l.Population,
        l.Alive,
        e.Rate_Health,
        e.Pending_Health,
        worst.System AS Worst_System,
        worst.[Status] AS Worst_Status
    FROM dbo.Levels AS l
    INNER JOIN dbo.Level_Effects AS e ON e.[Level] = l.[Level]
    OUTER APPLY (
        SELECT TOP (1) ls.System, ls.[Status]
        FROM dbo.Level_Systems AS ls
        WHERE ls.[Level] = l.[Level]
        ORDER BY ls.[Status] ASC, ls.System ASC
    ) AS worst
    ORDER BY l.[Level];
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_LevelSummary]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE PROCEDURE [dbo].[usp_LevelSummary]
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        [Level],
        COUNT(*) AS Population,
        ROUND(AVG(CONVERT(FLOAT, Money)), 0) AS Avg_Money,
        ROUND(AVG(CONVERT(FLOAT, Health)), 1) AS Avg_Health
    FROM dbo.Residents
    GROUP BY [Level]
    ORDER BY [Level];
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_RecomputeRates]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

/* ---------- 3. Procedures ---------- */
CREATE   PROCEDURE [dbo].[usp_RecomputeRates]
    @Level INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    -- damage = max_rate * (threshold - status) / threshold, only below the threshold
    -- heal   = 0.10 while food >= 80
    -- cure   = 0.00005 .. 0.0003 while medicine >= 80
    UPDATE e SET
        Rate_Health = COALESCE((
            SELECT SUM(st.Max_Rate * CASE WHEN st.Threshold - ls.[Status] > 0
                                          THEN st.Threshold - ls.[Status] ELSE 0 END / st.Threshold)
            FROM dbo.Level_Systems AS ls
            JOIN dbo.System_Types AS st ON st.System = ls.System
            WHERE ls.[Level] = e.[Level] AND st.Effect_Stat = N'health'), 0),
        Rate_Money = COALESCE((
            SELECT SUM(st.Max_Rate * CASE WHEN st.Threshold - ls.[Status] > 0
                                          THEN st.Threshold - ls.[Status] ELSE 0 END / st.Threshold)
            FROM dbo.Level_Systems AS ls
            JOIN dbo.System_Types AS st ON st.System = ls.System
            WHERE ls.[Level] = e.[Level] AND st.Effect_Stat = N'money'), 0),
        Rate_Heal = COALESCE((
            SELECT CASE WHEN ls.[Status] >= 80.0 THEN 0.10 ELSE 0 END
            FROM dbo.Level_Systems AS ls
            WHERE ls.[Level] = e.[Level] AND ls.System = N'food'), 0),
        Rate_Cure = COALESCE((
            SELECT CASE WHEN ls.[Status] >= 80.0
                        THEN 0.00005 + (0.0003 - 0.00005) * (ls.[Status] - 80.0) / 20.0
                        ELSE 0 END
            FROM dbo.Level_Systems AS ls
            WHERE ls.[Level] = e.[Level] AND ls.System = N'medicine'), 0)
    FROM dbo.Level_Effects AS e
    WHERE @Level IS NULL OR e.[Level] = @Level;
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_RefreshPopulation]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[usp_RefreshPopulation]
AS
BEGIN
    SET NOCOUNT ON;
    -- full recount from small indexes: population, living, and the LIVING workers standing on
    -- each level (walking workers do not count anywhere)
    DECLARE @Pop TABLE ([Level] INT PRIMARY KEY, N BIGINT);
    DECLARE @Dead TABLE ([Level] INT, Work NVARCHAR(30), N BIGINT);
    DECLARE @Tot TABLE ([Level] INT, Work NVARCHAR(30), N BIGINT);
    DECLARE @Mov TABLE ([Level] INT, Work NVARCHAR(30), N BIGINT);

    INSERT INTO @Pop SELECT [Level], COUNT_BIG(*) FROM dbo.Residents GROUP BY [Level];
    INSERT INTO @Dead SELECT [Level], Work, COUNT_BIG(*) FROM dbo.Residents WHERE Health = 0 GROUP BY [Level], Work;
    INSERT INTO @Tot SELECT [Level], Work, COUNT_BIG(*) FROM dbo.Residents
        WHERE Work IN (N'engineer', N'farmer', N'medic') GROUP BY [Level], Work;
    INSERT INTO @Mov SELECT [Level], Work, COUNT_BIG(*) FROM dbo.Residents
        WHERE Moving = 1 AND Health > 0 GROUP BY [Level], Work;

    UPDATE l SET
        Population = ISNULL(p.N, 0),
        Alive      = ISNULL(p.N, 0) - ISNULL((SELECT SUM(d.N) FROM @Dead d WHERE d.[Level] = l.[Level]), 0),
        Engineers  = ISNULL((SELECT SUM(t.N) FROM @Tot t WHERE t.[Level] = l.[Level] AND t.Work = N'engineer'), 0)
                   - ISNULL((SELECT SUM(d.N) FROM @Dead d WHERE d.[Level] = l.[Level] AND d.Work = N'engineer'), 0)
                   - ISNULL((SELECT SUM(m.N) FROM @Mov m WHERE m.[Level] = l.[Level] AND m.Work = N'engineer'), 0),
        Farmers    = ISNULL((SELECT SUM(t.N) FROM @Tot t WHERE t.[Level] = l.[Level] AND t.Work = N'farmer'), 0)
                   - ISNULL((SELECT SUM(d.N) FROM @Dead d WHERE d.[Level] = l.[Level] AND d.Work = N'farmer'), 0)
                   - ISNULL((SELECT SUM(m.N) FROM @Mov m WHERE m.[Level] = l.[Level] AND m.Work = N'farmer'), 0),
        Medics     = ISNULL((SELECT SUM(t.N) FROM @Tot t WHERE t.[Level] = l.[Level] AND t.Work = N'medic'), 0)
                   - ISNULL((SELECT SUM(d.N) FROM @Dead d WHERE d.[Level] = l.[Level] AND d.Work = N'medic'), 0)
                   - ISNULL((SELECT SUM(m.N) FROM @Mov m WHERE m.[Level] = l.[Level] AND m.Work = N'medic'), 0)
    FROM dbo.Levels AS l
    LEFT JOIN @Pop AS p ON p.[Level] = l.[Level];
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_SetSystemStatus]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

/*==============================================================
  7. CHANGE SYSTEM STATUS
==============================================================*/
CREATE PROCEDURE [dbo].[usp_SetSystemStatus]
    @Level INT,
    @System NVARCHAR(50),
    @Status FLOAT,
    @SimTime FLOAT = 0,
    @WriteLog BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Status < 0 SET @Status = 0;
    IF @Status > 100 SET @Status = 100;

    BEGIN TRANSACTION;

    UPDATE dbo.Level_Systems
    SET [Status] = @Status
    WHERE [Level] = @Level AND System = @System;

    IF @@ROWCOUNT = 0
    BEGIN
        ROLLBACK TRANSACTION;
        THROW 50001, 'System does not exist on the specified level.', 1;
    END;

    IF @WriteLog = 1
    BEGIN
        INSERT INTO dbo.Event_Log (Sim_Time, [Level], System, Message)
        VALUES (@SimTime, @Level, @System,
                CONCAT(@System, N' set to ', CONVERT(NVARCHAR(20), ROUND(@Status, 0)), N'%'));
    END;

    COMMIT TRANSACTION;

    EXEC dbo.usp_RecomputeRates @Level = @Level;
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_SystemMatrix]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE PROCEDURE [dbo].[usp_SystemMatrix]
AS
BEGIN
    SET NOCOUNT ON;

    SELECT [Level], System, [Status]
    FROM dbo.Level_Systems
    ORDER BY [Level], System;
END;
GO
/****** Object:  StoredProcedure [dbo].[usp_Tick]    Script Date: 20/11/2026 8:56:46 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[usp_Tick]
    @DeltaSeconds FLOAT
AS
BEGIN
    SET NOCOUNT ON;
    IF @DeltaSeconds < 0
        THROW 50003, 'Delta seconds cannot be negative.', 1;
    UPDATE dbo.Level_Effects SET
        Pending_Health = Pending_Health + Rate_Health * @DeltaSeconds,
        Pending_Money  = Pending_Money  + Rate_Money  * @DeltaSeconds,
        Pending_Heal   = Pending_Heal   + Rate_Heal   * @DeltaSeconds,
        Pending_Cure   = Pending_Cure   + Rate_Cure   * @DeltaSeconds;
END;
GO
