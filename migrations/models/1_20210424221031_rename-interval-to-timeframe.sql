-- upgrade --
ALTER TABLE "candle" RENAME COLUMN "interval" TO "timeframe";
ALTER TABLE "candle" DROP CONSTRAINT "uid_candle_instrum_225ae4";
CREATE UNIQUE INDEX "uid_candle_instrum_eba827" ON "candle" ("instrument_id", "timeframe", "time");
-- downgrade --
ALTER TABLE "candle" RENAME COLUMN "timeframe" TO "interval";
ALTER TABLE "candle" DROP CONSTRAINT "uid_candle_instrum_eba827";
CREATE UNIQUE INDEX "uid_candle_instrum_225ae4" ON "candle" ("instrument_id", "interval", "time");
