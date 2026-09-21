"""One-off portfolio entry: DFH, 2026-09-16, per the locked paper-portfolio spec.

Position #2. DFH signalled 2026-09-14 (day-0 $12.70) and was KEPT on per-arrival
review after reading the Q2'26 10-Q and FY25 10-K — see the ResearchNote recorded
2026-09-16. LUCK, the other signal from the same backfill, was dropped and is NOT
entered.

Cloned from enter_uuuu_2026-07-14.py with ONE structural addition: UUUU was the
launch trade and had $100K of cash sitting there. Since then cash rests at the
$1,000 buffer with everything else in SGOV, so this script must FIRST liquidate
~$5,000 of SGOV to fund the slice. The UUUU script would abort here on
`cash < SLICE`. Per the locked spec: "SGOV sweep ... auto-liquidated to fund new
buys."

Order of operations:
  1. Guards (paper endpoint, keys, market open today, DFH tradable)
  2. SELL $5,000 of SGOV -> cash goes $1,000 -> ~$6,000
  3. BUY $5,000 DFH in 3 market tranches -> cash back to ~$1,000
  4. Re-sweep any residual above the $1,000 buffer back into SGOV

Tranche timing — the spec says a mid-session signal has its "remaining tranches
compress into the day". It is already past the standard 10:00/12:30 slots, so
this spaces three tranches evenly from start to 15:30 ET rather than firing two
back-to-back at the same price, which would defeat the point of tranching.

Resumable: counts today's already-filled DFH buys on start and skips that many,
so a crash/restart never double-buys. The SGOV sell is likewise skipped if cash
already covers the slice.

Run detached inside the backend container:
    docker exec -d lookinsight-backend python enter_dfh_2026-09-16.py
Log: /app/backend/enter_dfh_2026-09-16.log (inside container)

Default = DRY-RUN (prints the plan, places NO orders). Pass --commit to trade.
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

ET = ZoneInfo("America/New_York")
SYMBOL = "DFH"
SWEEP_SYMBOL = "SGOV"
SLICE = 5000.00
TRANCHE_NOTIONALS = [1666.67, 1666.67, 1666.66]
LAST_TRANCHE_ET = (15, 30)
CASH_BUFFER = 1000.00
# Never fund to the exact cent. CASH_BUFFER is a STANDING buffer, not a tranche
# cushion — once it is set aside, exact funding leaves nothing for a fill that
# slips above its notional, a fee, or a concurrent entry drawing the same cash.
# 2026-09-21: LMB and MCFT ran the same day; the second read the first's reserved
# cash as spare, under-funded by a full slice, and the later tranches would have
# filled on MARGIN rather than failing loudly. Manohar: keep at least 5% spare.
FUNDING_CUSHION = 1.05

SIGNAL_ID = "CLUSTER-0001825088-2026-09-14"
SIGNAL_DATE = "2026-09-14"
DAY0_PRICE = 12.70
EXIT_DATE = "2026-12-13"  # day-90; a Sunday, resolves forward at exit time

LOG_PATH = Path(__file__).parent / "enter_dfh_2026-09-16.log"


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


def latest_price(client: httpx.Client, symbol: str) -> float:
    r = client.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                   headers=headers())
    r.raise_for_status()
    return float(r.json()["trade"]["p"])


def await_fill(client: httpx.Client, order: dict) -> dict:
    for _ in range(60):
        o = get(client, f"/v2/orders/{order['id']}")
        if o["status"] == "filled":
            return o
        if o["status"] in ("canceled", "expired", "rejected"):
            raise RuntimeError(f"order {o['id']} ended {o['status']}")
        time.sleep(5)
    raise RuntimeError(f"order {order['id']} not filled after 5 min (status={o['status']})")


def place_market(client: httpx.Client, symbol: str, side: str, notional: float,
                 fractionable: bool, last_price: float) -> dict:
    if fractionable:
        body = {"symbol": symbol, "notional": f"{notional:.2f}", "side": side,
                "type": "market", "time_in_force": "day"}
    else:
        qty = int(notional // last_price)
        if qty < 1:
            raise RuntimeError(f"{symbol}: notional {notional} < 1 share at ${last_price}")
        body = {"symbol": symbol, "qty": str(qty), "side": side,
                "type": "market", "time_in_force": "day"}
    return await_fill(client, post(client, "/v2/orders", body))


def filled_buys_today(client: httpx.Client, symbol: str) -> int:
    today_et = datetime.now(ET).strftime("%Y-%m-%d")
    orders = get(client, "/v2/orders", {
        "status": "closed", "symbols": symbol, "side": "buy",
        "after": f"{today_et}T00:00:00-04:00", "limit": 20,
    })
    return sum(1 for o in orders if o["status"] == "filled")


def tranche_targets(now: datetime, count: int) -> list[datetime]:
    """Evenly space `count` tranches between now and 15:30 ET (compress rule)."""
    last = now.replace(hour=LAST_TRANCHE_ET[0], minute=LAST_TRANCHE_ET[1],
                       second=0, microsecond=0)
    start = now + timedelta(minutes=1)
    if count <= 1 or last <= start:
        return [start] * count
    step = (last - start) / (count - 1)
    return [start + step * i for i in range(count)]


def main(commit: bool):
    if "paper-api" not in settings.ALPACA_BASE_URL:
        log("ABORT: not a paper endpoint — this script only runs against paper trading.")
        sys.exit(1)
    if not settings.ALPACA_API_KEY:
        log("ABORT: Alpaca keys not configured.")
        sys.exit(1)

    with httpx.Client(timeout=20.0) as client:
        clock = get(client, "/v2/clock")
        log(f"Market clock: is_open={clock['is_open']}, next_close={clock['next_close']}")
        today_et = datetime.now(ET).date()
        if not clock["is_open"] and datetime.fromisoformat(clock["next_open"]).date() != today_et:
            log(f"ABORT: market does not open today ({today_et}). No orders placed.")
            sys.exit(1)
        if not clock["is_open"]:
            log("ABORT: market not open right now — this script places market orders only.")
            sys.exit(1)

        account = get(client, "/v2/account")
        cash = float(account["cash"])
        log(f"Account {account['account_number']}: equity ${float(account['equity']):,.2f}, "
            f"cash ${cash:,.2f}")

        asset = get(client, f"/v2/assets/{SYMBOL}")
        if not asset.get("tradable"):
            log(f"ABORT: {SYMBOL} not tradable on Alpaca.")
            sys.exit(1)
        fractionable = bool(asset.get("fractionable"))
        px = latest_price(client, SYMBOL)
        log(f"{SYMBOL}: tradable=True, fractionable={fractionable}, last ${px:.2f}  "
            f"(day-0 ${DAY0_PRICE:.2f}, shortfall if filled here "
            f"{(px - DAY0_PRICE) / DAY0_PRICE * 100:+.2f}%)")

        already = filled_buys_today(client, SYMBOL)
        if already:
            log(f"RESUME: {already} {SYMBOL} tranche(s) already filled today — skipping that many.")
        remaining = [n for i, n in enumerate(TRANCHE_NOTIONALS, start=1) if i > already]
        need = round(sum(remaining), 2)

        targets = tranche_targets(datetime.now(ET), len(remaining))
        log(f"Plan: fund ${SLICE:,.2f} by selling {SWEEP_SYMBOL}, then buy "
            f"{len(remaining)} tranche(s) totalling ${need:,.2f} at "
            + ", ".join(t.strftime("%H:%M") for t in targets) + " ET")
        log(f"Exit day-90 = {EXIT_DATE} (signal {SIGNAL_ID}, date {SIGNAL_DATE})")

        if not commit:
            log("DRY-RUN: no orders placed. Re-run with --commit to trade.")
            return

        # --- 1. fund the slice out of SGOV -------------------------------
        if cash < need * FUNDING_CUSHION + CASH_BUFFER:
            raise_amt = round(need * FUNDING_CUSHION + CASH_BUFFER - cash, 2)
            sgov = get(client, f"/v2/assets/{SWEEP_SYMBOL}")
            log(f"Funding: selling ${raise_amt:,.2f} of {SWEEP_SYMBOL} "
                f"(cash ${cash:,.2f} < need ${need:,.2f} + buffer ${CASH_BUFFER:,.0f})")
            o = place_market(client, SWEEP_SYMBOL, "sell", raise_amt,
                             bool(sgov.get("fractionable")), latest_price(client, SWEEP_SYMBOL))
            log(f"Funding SELL FILLED: {float(o['filled_qty'])} {SWEEP_SYMBOL} @ "
                f"${float(o['filled_avg_price']):.4f}")
            cash = float(get(client, "/v2/account")["cash"])
            log(f"Cash after funding: ${cash:,.2f}")
        else:
            log(f"Funding: cash ${cash:,.2f} already covers the slice — no {SWEEP_SYMBOL} sale.")

        # --- 2. buy the slice in tranches --------------------------------
        fills = []
        for i, (notional, target) in enumerate(zip(remaining, targets), start=already + 1):
            if datetime.now(ET) < target:
                log(f"Tranche {i}/3: waiting until {target.strftime('%H:%M ET')}")
                wait_until(target)
            next_close = datetime.fromisoformat(get(client, "/v2/clock")["next_close"])
            if datetime.now(ET) > next_close - timedelta(minutes=5):
                log(f"Tranche {i}/3: within 5 min of close — placing immediately.")
            o = place_market(client, SYMBOL, "buy", notional, fractionable,
                             0.0 if fractionable else latest_price(client, SYMBOL))
            qty, avg = float(o["filled_qty"]), float(o["filled_avg_price"])
            fills.append((qty, avg))
            log(f"Tranche {i}/3 FILLED: {qty} sh @ ${avg:.4f} (${qty * avg:,.2f})")

        if fills:
            tq = sum(q for q, _ in fills)
            avg_all = sum(q * p for q, p in fills) / tq
            log(f"{SYMBOL} entry: {tq:.4f} sh, avg ${avg_all:.4f}, "
                f"shortfall {(avg_all - DAY0_PRICE) / DAY0_PRICE * 100:+.2f}% vs day-0 ${DAY0_PRICE:.2f}")

        # --- 3. re-sweep residual ----------------------------------------
        cash = float(get(client, "/v2/account")["cash"])
        residual = round(cash - CASH_BUFFER, 2)
        if residual < 100:
            log(f"Re-sweep: cash ${cash:,.2f} leaves ${residual:,.2f} above the "
                f"${CASH_BUFFER:,.0f} buffer — nothing meaningful, skipping.")
        else:
            sgov = get(client, f"/v2/assets/{SWEEP_SYMBOL}")
            o = place_market(client, SWEEP_SYMBOL, "buy", residual,
                             bool(sgov.get("fractionable")), latest_price(client, SWEEP_SYMBOL))
            log(f"Re-sweep FILLED: {float(o['filled_qty'])} {SWEEP_SYMBOL} @ "
                f"${float(o['filled_avg_price']):.4f} (${residual:,.2f})")

        account = get(client, "/v2/account")
        log(f"DONE. Equity ${float(account['equity']):,.2f}, cash ${float(account['cash']):,.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="place real paper orders (default: dry-run)")
    main(ap.parse_args().commit)
