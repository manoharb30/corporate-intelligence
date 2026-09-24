"""Day-90 exit: UUUU, 2026-10-07, per the locked paper-portfolio spec.

FIRST exit the portfolio has ever made. Everything before this has been buying.

Sells the whole UUUU position in 3 same-day market tranches at 10:00 / 12:30 /
15:30 ET, then sweeps the proceeds into SGOV above the cash buffer. Three
tranches, NOT a single market sell — Manohar corrected that explicitly on
2026-07-14, and the exit mirrors the entry style so execution is measured the
same way at both ends.

  Signal   CLUSTER-0001385849-2026-07-09, day-0 $13.49
  Entry    2026-07-14, 376.047447 sh @ avg $13.2961, shortfall -1.44%
  Day-90   2026-10-07 (Wed)

TIMING. The SALE happens ON day-90. That is different from MATURATION, which per
feedback_maturation_timing may only run AFTER day-90 has fully passed — so the
signal row is matured separately on 2026-10-08 or later, by a mature_* script.
Do not conflate the two: this script touches the broker, not the cohort.

SIZING. Sells by SHARE QUANTITY, not notional. Tranches 1 and 2 each sell a
third of the opening quantity; tranche 3 sells WHATEVER REMAINS, which
guarantees the position closes to zero with no fractional dust left behind. A
notional sell would leave a residue that quietly persists as an open position.

RESUMABLE. Counts today's already-filled UUUU sells on start and skips that many.
Because tranche 3 closes out the remainder, a restart mid-way still ends flat.

SEQUENCING. Single name, so no concurrency risk here — but note the lesson from
2026-09-21: when two portfolio scripts ran the same day they each read a shared
cash balance neither owned, and both the funding and the re-sweep double-counted.
If a future exit day handles more than one name, establish the day's cash
position once and sweep ONCE at the end, not per script.

Run detached inside the backend container:
    docker exec -d lookinsight-backend python exit_uuuu_2026-10-07.py --commit
Log: /app/backend/exit_uuuu_2026-10-07.log (inside container)

Default = DRY-RUN (prints the plan, places NO orders). Pass --commit to trade.
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from app.config import settings
from app.db.neo4j_client import Neo4jClient

ET = ZoneInfo("America/New_York")
SYMBOL = "UUUU"
SWEEP_SYMBOL = "SGOV"
CASH_BUFFER = 1000.00
TRANCHE_TIMES_ET = [(10, 0), (12, 30), (15, 30)]
SWEEP_TIME_ET = (15, 40)

SIGNAL_ID = "CLUSTER-0001385849-2026-07-09"
DAY0_PRICE = 13.49
DAY90_DATE = "2026-10-07"
SIGNAL_DATE = "2026-07-09"   # day 0 — when the signal fired
ENTRY_DATE = "2026-07-14"    # when we actually bought (detection + review lag)
ENTRY_AVG = 13.296115
ENTRY_QTY = 376.047447

LOG_PATH = Path(__file__).parent / "exit_uuuu_2026-10-07.log"


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
        remaining = (target_et - datetime.now(ET)).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def await_fill(client: httpx.Client, order: dict) -> dict:
    for _ in range(60):
        o = get(client, f"/v2/orders/{order['id']}")
        if o["status"] == "filled":
            return o
        if o["status"] in ("canceled", "expired", "rejected"):
            raise RuntimeError(f"order {o['id']} ended {o['status']}")
        time.sleep(5)
    raise RuntimeError(f"order {order['id']} not filled after 5 min (status={o['status']})")


def position_qty(client: httpx.Client, symbol: str) -> float:
    for p in get(client, "/v2/positions"):
        if p["symbol"] == symbol:
            return float(p["qty"])
    return 0.0


def filled_sells_today(client: httpx.Client, symbol: str) -> int:
    today_et = datetime.now(ET).strftime("%Y-%m-%d")
    orders = get(client, "/v2/orders", {
        "status": "closed", "symbols": symbol, "side": "sell",
        "after": f"{today_et}T00:00:00-04:00", "limit": 20,
    })
    return sum(1 for o in orders if o["status"] == "filled")


def sell_qty(client: httpx.Client, symbol: str, qty: float) -> dict:
    body = {"symbol": symbol, "qty": f"{qty:.6f}", "side": "sell",
            "type": "market", "time_in_force": "day"}
    return await_fill(client, post(client, "/v2/orders", body))


async def record_exit(fills: list[tuple[float, float]], closed_qty: float, proceeds: float):
    """Durable exit record — the /portfolio page reads LIVE Alpaca positions, so a
    closed position vanishes from it entirely. Without this the first completed
    round trip would leave no position-level trace: entry, exit, realised return
    and both shortfalls would be gone from everything but the log file.
    Follows the (:PortfolioSkip) precedent already referenced in
    alpaca_portfolio_service.
    """
    blended = proceeds / closed_qty if closed_qty else 0.0
    realised = (blended - ENTRY_AVG) / ENTRY_AVG * 100 if ENTRY_AVG else 0.0
    await Neo4jClient.connect()
    await Neo4jClient.execute_query(
        """
        MERGE (pe:PortfolioExit {signal_id: $signal_id})
        SET pe.ticker = $ticker,
            pe.signal_date = $signal_date,
            pe.entry_date = $entry_date,
            pe.exit_date = $exit_date,
            pe.day0_price = $day0_price,
            pe.entry_avg = $entry_avg,
            pe.entry_qty = $entry_qty,
            pe.exit_avg = $exit_avg,
            pe.exit_qty = $exit_qty,
            pe.proceeds = $proceeds,
            pe.realised_return_pct = $realised,
            pe.tranche_prices = $tranche_prices,
            pe.recorded_at = datetime()
        RETURN pe.ticker AS t
        """,
        {
            "signal_id": SIGNAL_ID, "ticker": SYMBOL, "exit_date": DAY90_DATE,
            "signal_date": SIGNAL_DATE, "entry_date": ENTRY_DATE,
            "day0_price": DAY0_PRICE, "entry_avg": ENTRY_AVG, "entry_qty": ENTRY_QTY,
            "exit_avg": round(blended, 6), "exit_qty": round(closed_qty, 6),
            "proceeds": round(proceeds, 2), "realised": round(realised, 2),
            "tranche_prices": [round(p, 4) for _, p in fills],
        },
    )
    log(f"PortfolioExit recorded: exit_avg ${blended:.4f}, realised {realised:+.2f}% vs entry")


def main(commit: bool):
    if "paper-api" not in settings.ALPACA_BASE_URL:
        log("ABORT: not a paper endpoint — this script only runs against paper trading.")
        sys.exit(1)
    if not settings.ALPACA_API_KEY:
        log("ABORT: Alpaca keys not configured.")
        sys.exit(1)

    today = datetime.now(ET).strftime("%Y-%m-%d")
    if today < DAY90_DATE:
        log(f"ABORT: today {today} is before day-90 {DAY90_DATE}. Exit is a day-90 trade.")
        sys.exit(1)
    if today > DAY90_DATE:
        log(f"WARNING: today {today} is AFTER day-90 {DAY90_DATE} — exiting late. "
            f"The cohort still books its return at the {DAY90_DATE} close, so the "
            f"difference shows up as exit shortfall. Continuing.")

    with httpx.Client(timeout=20.0) as client:
        clock = get(client, "/v2/clock")
        log(f"Market clock: is_open={clock['is_open']}, next_close={clock['next_close']}")
        if not clock["is_open"]:
            log("ABORT: market not open — this script places market orders only.")
            sys.exit(1)

        qty = position_qty(client, SYMBOL)
        if qty <= 0:
            log(f"ABORT: no {SYMBOL} position to sell (qty={qty}).")
            sys.exit(1)
        acct = get(client, "/v2/account")
        log(f"Account {acct['account_number']}: equity ${float(acct['equity']):,.2f}, "
            f"cash ${float(acct['cash']):,.2f}")
        log(f"{SYMBOL} position: {qty:.6f} sh  (entry avg ${ENTRY_AVG:.4f}, "
            f"day-0 ${DAY0_PRICE:.2f})")

        already = filled_sells_today(client, SYMBOL)
        if already:
            log(f"RESUME: {already} {SYMBOL} sell tranche(s) already filled today — "
                f"skipping that many.")

        third = round(qty / 3, 6)
        plan = []
        for i, (hh, mm) in enumerate(TRANCHE_TIMES_ET, start=1):
            if i <= already:
                continue
            plan.append((i, hh, mm, "REMAINDER" if i == 3 else f"{third:.6f} sh"))
        log("Plan: " + "; ".join(f"T{i} {hh:02d}:{mm:02d} ET {w}" for i, hh, mm, w in plan))
        log(f"Then sweep proceeds above the ${CASH_BUFFER:,.0f} buffer into {SWEEP_SYMBOL}.")

        if not commit:
            log("DRY-RUN: no orders placed. Re-run with --commit to trade.")
            return

        fills: list[tuple[float, float]] = []
        for i, hh, mm, _ in plan:
            target = datetime.now(ET).replace(hour=hh, minute=mm, second=0, microsecond=0)
            if datetime.now(ET) < target:
                log(f"Tranche {i}/3: waiting until {target.strftime('%H:%M ET')}")
                wait_until(target)

            # Tranche 3 closes out whatever is left, so the position ends at zero
            # regardless of rounding or a partial earlier run.
            this_qty = position_qty(client, SYMBOL) if i == 3 else third
            if this_qty <= 0:
                log(f"Tranche {i}/3: nothing left to sell — position already flat.")
                break
            o = sell_qty(client, SYMBOL, this_qty)
            fq, fp = float(o["filled_qty"]), float(o["filled_avg_price"])
            fills.append((fq, fp))
            log(f"Tranche {i}/3 SOLD: {fq} sh @ ${fp:.4f} (${fq * fp:,.2f})")

        remaining = position_qty(client, SYMBOL)
        if remaining > 0.000001:
            log(f"WARNING: {remaining:.6f} sh still held after all tranches. Investigate.")

        if fills:
            closed = sum(q for q, _ in fills)
            proceeds = sum(q * p for q, p in fills)
            blended = proceeds / closed
            log(f"{SYMBOL} EXIT: {closed:.6f} sh, avg ${blended:.4f}, "
                f"proceeds ${proceeds:,.2f}")
            log(f"  vs entry ${ENTRY_AVG:.4f} -> realised {(blended - ENTRY_AVG) / ENTRY_AVG * 100:+.2f}%")
            log(f"  vs day-0 ${DAY0_PRICE:.2f} -> {(blended - DAY0_PRICE) / DAY0_PRICE * 100:+.2f}%")
            log("  NOTE: the cohort books this signal at the day-90 CLOSE, not at these")
            log("  fills. The gap between them is exit shortfall and is only computable")
            log("  once the close is published — the maturation run reports it.")
            asyncio.run(record_exit(fills, closed, proceeds))

        # Sweep proceeds — once, after all tranches.
        sweep_target = datetime.now(ET).replace(hour=SWEEP_TIME_ET[0], minute=SWEEP_TIME_ET[1],
                                                second=0, microsecond=0)
        if datetime.now(ET) < sweep_target:
            log(f"Sweep: waiting until {sweep_target.strftime('%H:%M ET')}")
            wait_until(sweep_target)

        cash = float(get(client, "/v2/account")["cash"])
        amt = round(cash - CASH_BUFFER, 2)
        if amt < 100:
            log(f"Sweep: cash ${cash:,.2f} leaves ${amt:,.2f} above the buffer — skipping.")
        else:
            sgov = get(client, f"/v2/assets/{SWEEP_SYMBOL}")
            body = ({"symbol": SWEEP_SYMBOL, "notional": f"{amt:.2f}"}
                    if sgov.get("fractionable") else
                    {"symbol": SWEEP_SYMBOL, "qty": str(int(amt // 100))})
            body |= {"side": "buy", "type": "market", "time_in_force": "day"}
            o = await_fill(client, post(client, "/v2/orders", body))
            log(f"Sweep FILLED: {float(o['filled_qty'])} {SWEEP_SYMBOL} @ "
                f"${float(o['filled_avg_price']):.4f} (${amt:,.2f})")

        acct = get(client, "/v2/account")
        log(f"DONE. Equity ${float(acct['equity']):,.2f}, cash ${float(acct['cash']):,.2f}")
        log(f"NEXT: mature the signal on {DAY90_DATE} + 1 or later — see "
            f"feedback_maturation_timing. This script did NOT touch the cohort.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="place real paper orders (default: dry-run)")
    main(ap.parse_args().commit)
