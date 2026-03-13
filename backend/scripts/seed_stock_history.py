import argparse
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.mongo import mongo_db
from app.services.finnhub_service import FinnhubService


def seed_symbol(symbol: str, days: int, resolution: str) -> int:
    if not settings.FINNHUB_API_KEY:
        raise RuntimeError(
            "FINNHUB_API_KEY is not set. Add it to backend/.env then restart."
        )

    sym = symbol.upper().strip()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    from_unix = int(start.timestamp())
    to_unix = int(now.timestamp())

    service = FinnhubService()
    data = service.get_candles(sym, resolution, from_unix, to_unix)
    if data.get("s") != "ok":
        raise RuntimeError(f"Finnhub candles error: {data}")

    ts = data.get("t") or []
    closes = data.get("c") or []
    if not ts or not closes:
        return 0

    col = mongo_db.get_collection("stock_history")
    # Unique constraint via compound key in code (symbol+t)
    bulk = []
    for t, c in zip(ts, closes):
        bulk.append(
            {
                "updateOne": {
                    "filter": {"symbol": sym, "t": int(t)},
                    "update": {
                        "$set": {
                            "symbol": sym,
                            "t": int(t),
                            "c": float(c),
                            "resolution": resolution,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                    "upsert": True,
                }
            }
        )

    if bulk:
        result = col.bulk_write(bulk, ordered=False)
        return int(result.upserted_count + result.modified_count)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed MongoDB stock_history collection from Finnhub candles."
    )
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. AAPL)")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="How many days of history to fetch (default: 365)",
    )
    parser.add_argument(
        "--resolution",
        default="D",
        help='Finnhub candle resolution (default: "D")',
    )
    args = parser.parse_args()

    n = seed_symbol(args.symbol, args.days, args.resolution)
    print(f"Seeded {n} points for {args.symbol.upper()} into MongoDB stock_history.")


if __name__ == "__main__":
    main()

