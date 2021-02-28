-- upgrade --
CREATE TABLE IF NOT EXISTS "instrument" (
    "figi" VARCHAR(12) NOT NULL  PRIMARY KEY,
    "type" VARCHAR(1) NOT NULL,
    "name" TEXT NOT NULL,
    "ticker" VARCHAR(16) NOT NULL UNIQUE,
    "currency" VARCHAR(3) NOT NULL  DEFAULT 'USD',
    "price_increment" DECIMAL(5,2) NOT NULL,
    "imported_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ
);
COMMENT ON COLUMN "instrument"."type" IS 'STOCK: s\nBOND: b\nCURRENCY: c';
COMMENT ON COLUMN "instrument"."currency" IS 'USD: USD\nRUB: RUB\nEUR: EUR';
CREATE TABLE IF NOT EXISTS "candle" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "interval" VARCHAR(6) NOT NULL,
    "time" TIMESTAMPTZ NOT NULL,
    "open" DECIMAL(8,2) NOT NULL,
    "high" DECIMAL(8,2) NOT NULL,
    "low" DECIMAL(8,2) NOT NULL,
    "close" DECIMAL(8,2) NOT NULL,
    "volume" INT NOT NULL,
    "instrument_id" VARCHAR(12) NOT NULL REFERENCES "instrument" ("figi") ON DELETE CASCADE,
    CONSTRAINT "uid_candle_instrum_225ae4" UNIQUE ("instrument_id", "interval", "time")
);
CREATE INDEX IF NOT EXISTS "idx_candle_instrum_225ae4" ON "candle" ("instrument_id", "interval", "time");
COMMENT ON COLUMN "candle"."interval" IS 'M1: 1min\nM5: 5min\nM10: 10min\nM30: 30min\nH1: hour\nD1: day\nD7: week\nD30: month';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(20) NOT NULL,
    "content" JSONB NOT NULL
);
