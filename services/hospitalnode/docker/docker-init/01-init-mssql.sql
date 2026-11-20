-- Run by docker-start/01-start-mssql.sh with sqlcmd -v SERMON_DB_USER=... SERMON_DB_PASSWORD=...
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'serMonDb')
BEGIN
    CREATE DATABASE serMonDB;
END
GO

USE serMonDB;
GO

IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = '$(SERMON_DB_USER)')
BEGIN
    CREATE LOGIN [$(SERMON_DB_USER)] WITH PASSWORD = '$(SERMON_DB_PASSWORD)';
END
GO

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = '$(SERMON_DB_USER)')
BEGIN
    CREATE USER [$(SERMON_DB_USER)] FOR LOGIN [$(SERMON_DB_USER)];
END
GO


-- ENABLE CDC

IF (SELECT is_cdc_enabled
    FROM sys.databases
    WHERE name = 'serMonDB') = 0
    BEGIN
        EXEC sys.sp_cdc_enable_db;
        PRINT 'CDC enabled on Database level.';
    END
GO


-- Grant db_owner so Debezium can read the cdc schema and transaction log
ALTER ROLE [db_owner] ADD MEMBER [$(SERMON_DB_USER)];
GO

-- (Optional but recommended) Grant VIEW DATABASE STATE permissions
GRANT VIEW DATABASE STATE TO [$(SERMON_DB_USER)];
GO

