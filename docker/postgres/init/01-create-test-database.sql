SELECT 'CREATE DATABASE gridops_test'
WHERE NOT EXISTS (
    SELECT
    FROM pg_database
    WHERE datname = 'gridops_test'
)\gexec