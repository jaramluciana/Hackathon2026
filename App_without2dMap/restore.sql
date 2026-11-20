-- Run in SSMS (connected to .\SQLEXPRESS). Change the path below to where you put the .bak
DECLARE @data NVARCHAR(400) = CONVERT(NVARCHAR(400), SERVERPROPERTY('InstanceDefaultDataPath'));
DECLARE @log  NVARCHAR(400) = CONVERT(NVARCHAR(400), SERVERPROPERTY('InstanceDefaultLogPath'));
DECLARE @sql  NVARCHAR(MAX) = N'
RESTORE DATABASE ResidentInfors
FROM DISK = N''C:\HollowCity\db\ResidentInfors.bak''
WITH REPLACE,
     MOVE N''ResidentInfors''     TO N''' + @data + N'ResidentInfors.mdf'',
     MOVE N''ResidentInfors_log'' TO N''' + @log  + N'ResidentInfors_log.ldf'';';
EXEC (@sql);