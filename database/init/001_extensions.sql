-- =============================================================================
-- INTELORA — Database bootstrap
--
-- Runs once, on first initialisation of an empty data volume, before the
-- backend connects. Creates the extensions the Telemetry Layer depends on.
-- Table creation and hypertable conversion are owned by the backend
-- (app/database/init_db.py) so that schema and code stay in one place.
-- =============================================================================

-- Time-series storage for the telemetry hypertable.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Server-side UUID generation for primary keys.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Trigram indexes, used by asset and alert search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
