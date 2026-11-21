USE [ResidentInfors]
GO
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
	[Status] [nvarchar](10) NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Explore_Sectors]    Script Date: 20/11/2026 10:54:03 CH ******/
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
	[Notes] [nvarchar](300) NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Effects]    Script Date: 20/11/2026 10:54:03 CH ******/
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
	[Healed_To] [float] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Supply]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Level_Supply](
	[Level] [int] NOT NULL,
	[System] [nvarchar](50) NOT NULL,
	[Capacity] [float] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Level_Systems]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Level_Systems](
	[Level] [int] NOT NULL,
	[System] [nvarchar](50) NOT NULL,
	[Status] [float] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Levels]    Script Date: 20/11/2026 10:54:03 CH ******/
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
	[Medics] [int] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Clinics]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Clinics](
	[ClinicID] [int] IDENTITY(1,1) NOT NULL,
	[Level] [int] NOT NULL,
	[Name] [nvarchar](120) NOT NULL,
	[SlotsTotal] [int] NOT NULL,
	[SlotsUsed] [int] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Inventory]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Inventory](
	[ClinicID] [int] NOT NULL,
	[Item] [nvarchar](60) NOT NULL,
	[Quantity] [int] NOT NULL,
	[Reserve] [int] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Med_Notices]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Med_Notices](
	[NoticeID] [int] IDENTITY(1,1) NOT NULL,
	[Level] [int] NULL,
	[Message] [nvarchar](1000) NOT NULL,
	[CreatedAt] [datetime2](7) NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[Shelter_Capacity]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Shelter_Capacity](
	[Level] [int] NOT NULL,
	[Capacity] [int] NOT NULL,
	[Occupied] [int] NOT NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[System_Types]    Script Date: 20/11/2026 10:54:03 CH ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[System_Types](
	[System] [nvarchar](50) NOT NULL,
	[Group] [nvarchar](100) NOT NULL,
	[Effect_Stat] [nvarchar](10) NOT NULL,
	[Max_Rate] [float] NOT NULL,
	[Threshold] [float] NOT NULL
) ON [PRIMARY]
GO
ALTER TABLE [dbo].[Explore_Missions] ADD  DEFAULT ('open') FOR [Status]
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
ALTER TABLE [dbo].[Med_Clinics] ADD  DEFAULT ((0)) FOR [SlotsUsed]
GO
ALTER TABLE [dbo].[Med_Inventory] ADD  DEFAULT ((0)) FOR [Quantity]
GO
ALTER TABLE [dbo].[Med_Inventory] ADD  DEFAULT ((0)) FOR [Reserve]
GO
ALTER TABLE [dbo].[Med_Notices] ADD  DEFAULT (sysutcdatetime()) FOR [CreatedAt]
GO
ALTER TABLE [dbo].[Shelter_Capacity] ADD  DEFAULT ((0)) FOR [Capacity]
GO
ALTER TABLE [dbo].[Shelter_Capacity] ADD  DEFAULT ((0)) FOR [Occupied]
GO
ALTER TABLE [dbo].[System_Types] ADD  CONSTRAINT [DF_SystemTypes_Threshold]  DEFAULT ((100)) FOR [Threshold]
GO
ALTER TABLE [dbo].[Explore_Missions]  WITH CHECK ADD CHECK  (([Status]='closed' OR [Status]='paused' OR [Status]='open'))
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
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD CHECK  (([Capacity]>=(0)))
GO
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD CHECK  (([Occupied]>=(0)))
GO
ALTER TABLE [dbo].[Shelter_Capacity]  WITH CHECK ADD  CONSTRAINT [CK_ShelterCapacity] CHECK  (([Occupied]<=[Capacity]))
GO
ALTER TABLE [dbo].[Shelter_Capacity] CHECK CONSTRAINT [CK_ShelterCapacity]
GO
ALTER TABLE [dbo].[System_Types]  WITH CHECK ADD CHECK  (([Effect_Stat]=N'money' OR [Effect_Stat]=N'health'))
GO
ALTER TABLE [dbo].[System_Types]  WITH CHECK ADD  CONSTRAINT [CK_SystemTypes_Threshold] CHECK  (([Threshold]>(0) AND [Threshold]<=(100)))
GO
ALTER TABLE [dbo].[System_Types] CHECK CONSTRAINT [CK_SystemTypes_Threshold]
GO
