from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user


router = APIRouter()


MOCK_POSITIONS = [
    {
        "symbol": "AAPL",
        "name": "Apple Inc",
        "qty": 10,
        "avg_cost": 175.0,
        "current": 200.0,
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft Corp",
        "qty": 5,
        "avg_cost": 320.0,
        "current": 410.0,
    },
    {
        "symbol": "TSLA",
        "name": "Tesla Inc",
        "qty": 2,
        "avg_cost": 210.0,
        "current": 185.0,
    },
]


@router.get("/summary")
def portfolio_summary(user: dict = Depends(get_current_user)) -> dict:
    total_cost = sum(p["qty"] * p["avg_cost"] for p in MOCK_POSITIONS)
    total_value = sum(p["qty"] * p["current"] for p in MOCK_POSITIONS)
    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100) if total_cost else 0.0

    return {
        "user": {"email": user["email"]},
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_pct": round(pnl_pct, 2),
        "positions_count": len(MOCK_POSITIONS),
    }


@router.get("/positions")
def portfolio_positions(user: dict = Depends(get_current_user)) -> dict:
    enriched = []
    for p in MOCK_POSITIONS:
        cost = p["qty"] * p["avg_cost"]
        value = p["qty"] * p["current"]
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0.0
        enriched.append(
            {
                **p,
                "cost": round(cost, 2),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )
    return {"user": {"email": user["email"]}, "positions": enriched}


@router.get("/")
def portfolio_root(user: dict = Depends(get_current_user)) -> dict:
    # Backwards-compatible minimal route
    return portfolio_summary(user)
