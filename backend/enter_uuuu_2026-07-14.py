"""One-off portfolio entry: UUUU, 2026-07-14, per the locked paper-portfolio spec.

Buys a fixed $5,000 UUUU slice in 3 market-order tranches (~$1,666.67 each) at
10:00 / 12:30 / 15:30 ET, then sweeps free cash above a $1,000 buffer into SGOV
at ~15:35 ET. Paper account only (base URL guard below).

Resumable: counts today's already-filled UUUU buy orders on start and skips
that many tranches, so a crash/restart never double-buys.

Run detached inside the backend container:
    docker exec -d lookinsight-backend python enter_uuuu_2026-07-14.py
Log: /app/backend/enter_uuuu_2026-07-14.log (inside container)
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

ET = ZoneInfo("America/New_York")
SYMBOL = "UUUU"
SWEEP_SYMBOL = "SGOV"
SLICE = 5000.00
TRANCHE_NOTIONALS = [1666.67, 1666.67, 1666.66]
TRANCHE_TIMES_ET = [(10, 0), (12, 30), (15, 30)]
SWEEP_TIME_ET = (15, 35)
CASH_BUFFER = 1000.00

LOG_PATH = Path(__file__).parent / "enter_uuuu_2026-07-14.log"


def log(msg: str):
    line = f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def headers():
    return {
        "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
    }


def get(client: httpx.Client, path: str, params: dict | None = None):
    r = client.get(f"{settings.ALPACA_BASE_URL}{path}", headers=headers(), params=params or {})
    r.raise_for_status()
    return r.json()


def post(client: httpx.Client, path: str, body: dict):
    r = client.post(f"{settings.ALPACA_BASE_URL}{path}", headers=headers(), json=body)
    r.raise_for_status()
    return r.json()


def wait_until(target_et: datetime):
    while True:
        now = datetime.now(ET)
        remaining = (target_et - now).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def place_market_buy(client: httpx.Client, symbol: str, notional: float, fractionable: bool,
                     last_price: float) -> dict:
    if fractionable:
        body = {"symbol": symbol, "notional": f"{notional:.2f}", "side": "buy",
                "type": "market", "time_in_force": "day"}
    else:
        qty = int(notional // last_price)
        if qty < 1:
            raise RuntimeError(f"{symbol}: notional {notional} < 1 share at ${last_price}")
        body = {"symbol": symbol, "qty": str(qty), "side": "buy",
                "type": "market", "time_in_force": "day"}
    order = post(client, "/v2/orders", body)
    # poll to fill (paper fills near-instantly in market hours)
    for _ in range(60):
        o = get(client, f"/v2/orders/{order['id']}")
        if o["status"] == "filled":
            return o
        if o["status"] in ("canceled", "expired", "rejected"):
            raise RuntimeError(f"order {o['id']} ended {o['status']}")
        time.sleep(5)
    raise RuntimeError(f"order {order['id']} not filled after 5 min (status={o['status']})")


def filled_buys_today(client: httpx.Client, symbol: str) -> int:
    today_et = datetime.now(ET).strftime("%Y-%m-%d")
    orders = get(client, "/v2/orders", {
        "status": "closed", "symbols": symbol, "side": "buy",
        "after": f"{today_et}T00:00:00-04:00", "limit": 20,
    })
    return sum(1 for o in orders if o["status"] == "filled")


def main():
    if "paper-api" not in settings.ALPACA_BASE_URL:
        log("ABORT: not a paper endpoint — this script only runs against paper trading.")
        sys.exit(1)
    if not settings.ALPACA_API_KEY:
        log("ABORT: Alpaca keys not configured.")
        sys.exit(1)

    with httpx.Client(timeout=20.0) as client:
        clock = get(client, "/v2/clock")
        log(f"Market clock: is_open={clock['is_open']}, next_open={clock['next_open']}, next_close={clock['next_close']}")

        today_et = datetime.now(ET).date()
        next_close = datetime.fromisoformat(clock["next_close"])
        if not clock["is_open"] and datetime.fromisoformat(clock["next_open"]).date() != today_et:
            log(f"ABORT: market does not open today ({today_et}). No orders placed.")
            sys.exit(1)

        account = get(client, "/v2/account")
        cash = float(account["cash"])
        log(f"Account {account['account_number']}: cash ${cash:,.2f}")
        if cash < SLICE:
            log(f"ABORT: cash ${cash:,.2f} < slice ${SLICE:,.2f}")
            sys.exit(1)

        asset = get(client, f"/v2/assets/{SYMBOL}")
        fractionable = bool(asset.get("fractionable"))
        log(f"{SYMBOL}: tradable={asset.get('tradable')}, fractionable={fractionable}")
        if not asset.get("tradable"):
            log(f"ABORT: {SYMBOL} not tradable on Alpaca.")
            sys.exit(1)

        already = filled_buys_today(client, SYMBOL)
        if already:
            log(f"RESUME: {already} {SYMBOL} tranche(s) already filled today — skipping that many.")

        fills = []
        for i, ((hh, mm), notional) in enumerate(zip(TRANCHE_TIMES_ET, TRANCHE_NOTIONALS), start=1):
            if i <= already:
                continue
            target = datetime.now(ET).replace(hour=hh, minute=mm, second=0, microsecond=0)
            if datetime.now(ET) < target:
                log(f"Tranche {i}/3: waiting until {target.strftime('%H:%M ET')}")
                wait_until(target)
            # compress rule: never schedule past 15:55 ET
            if datetime.now(ET) > next_close - timedelta(minutes=5):
                log(f"Tranche {i}/3: too close to market close — placing immediately.")
            last_price = 0.0
            if not fractionable:
                # whole-share fallback needs a live price to size qty
                r = client.get(f"https://data.alpaca.markets/v2/stocks/{SYMBOL}/trades/latest",
                               headers=headers())
                r.raise_for_status()
                last_price = float(r.json()["trade"]["p"])
            o = place_market_buy(client, SYMBOL, notional, fractionable, last_price)
            qty = float(o["filled_qty"])
            avg = float(o["filled_avg_price"])
            fills.append((qty, avg))
            log(f"Tranche {i}/3 FILLED: {qty} sh @ ${avg:.4f} (${qty * avg:,.2f})")

        if fills or already == 3:
            total_qty = sum(q for q, _ in fills)
            if total_qty:
                avg_all = sum(q * p for q, p in fills) / total_qty
                log(f"{SYMBOL} entry tranches done this run: {total_qty:.4f} sh, avg ${avg_all:.4f}")

        # SGOV sweep at ~15:35 ET
        sweep_target = datetime.now(ET).replace(hour=SWEEP_TIME_ET[0], minute=SWEEP_TIME_ET[1],
                                                second=0, microsecond=0)
        if datetime.now(ET) < sweep_target:
            log(f"Sweep: waiting until {sweep_target.strftime('%H:%M ET')}")
            wait_until(sweep_target)

        account = get(client, "/v2/account")
        cash = float(account["cash"])
        sweep_amount = round(cash - CASH_BUFFER, 2)
        if sweep_amount < 100:
            log(f"Sweep: cash ${cash:,.2f} leaves nothing meaningful above the ${CASH_BUFFER:,.0f} buffer — skipping.")
        else:
            sgov = get(client, f"/v2/assets/{SWEEP_SYMBOL}")
            o = place_market_buy(client, SWEEP_SYMBOL, sweep_amount, bool(sgov.get("fractionable")), 100.6)
            log(f"Sweep FILLED: {float(o['filled_qty'])} {SWEEP_SYMBOL} @ ${float(o['filled_avg_price']):.4f} (${sweep_amount:,.2f})")

        account = get(client, "/v2/account")
        log(f"DONE. Account equity ${float(account['equity']):,.2f}, cash ${float(account['cash']):,.2f}")


if __name__ == "__main__":
    main()
