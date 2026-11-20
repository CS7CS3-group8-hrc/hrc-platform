#!/usr/bin/env bash
# Runs once on first start of the TimescaleDB container (/docker-entrypoint-initdb.d).
# Replaces 02-init-timescale.sql so the password comes from the environment, not the file.
# POSTGRES_DB already creates serMonTimescaleDB; do not CREATE DATABASE here.
set -euo pipefail
: "${SERMON_DB_PASSWORD:?SERMON_DB_PASSWORD is not set - copy .env.example to .env}"
SERMON_DB_USER="${SERMON_DB_USER:-sermon_admin}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "serMonTimescaleDB" \
     -v db_user="$SERMON_DB_USER" -v db_password="$SERMON_DB_PASSWORD" <<'SQL'
CREATE USER :"db_user" WITH PASSWORD :'db_password';
GRANT ALL PRIVILEGES ON DATABASE "serMonTimescaleDB" TO :"db_user";
CREATE EXTENSION IF NOT EXISTS timescaledb;
GRANT ALL ON SCHEMA public TO :"db_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO :"db_user";
SQL
