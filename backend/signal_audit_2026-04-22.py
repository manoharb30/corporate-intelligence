"""Per-signal audit for the 142 mature strong_buy cohort.

Produces one audit card per signal with:
  - stored vs actual cluster stats
  - underlying transactions
  - auto-raised red flags
  - direct SEC Form 4 URLs

Usage:
  python signal_audit_2026-04-22.py --limit 10    # first 10 by flag count
  python signal_audit_2026-04-22.py                # all 142
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

from app.db.neo4j_client import Neo4jClient

sys.stdout.reconfigure(line_buffering=True)


async def load_signal_and_txns(sp_row):
    sp = dict(sp_row)
    cik = sp["cik"]
    sig_date = sp["signal_date"][:10]

    txns = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik: $cik})-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)<-[:TRADED_BY]-(p:Person)
        WHERE t.transaction_code = 'P'
          AND (t.is_derivative IS NULL OR t.is_derivative = false)
          AND (t.total_value IS NOT NULL AND t.total_value > 0)
          AND date(substring(toString(t.transaction_date), 0, 10))
              >= date($sig_date) - duration({days: 30})
          AND date(substring(toString(t.transaction_date), 0, 10))
              <= date($sig_date)
        RETURN substring(toString(t.transaction_date), 0, 10) AS txn_date,
               substring(toString(t.filing_date), 0, 10) AS filed,
               p.name AS insider,
               t.insider_title AS title,
               t.shares AS shares,
               t.price_per_share AS price,
               t.total_value AS value,
               t.classification AS cls,
               t.accession_number AS acc,
               t.primary_document AS primary_doc,
               t.insider_cik AS insider_cik
        ORDER BY txn_date, insider
    """, {"cik": cik, "sig_date": sig_date})
    txns = [dict(t) for t in txns]

    # price_series first date (for IPO proximity check)
    comp = await Neo4jClient.execute_query("""
        MATCH (c:Company {cik: $cik})
        RETURN c.price_series AS ps, c.name AS name
    """, {"cik": cik})
    first_trade_date = None
    if comp:
        ps_str = comp[0].get("ps")
        if ps_str:
            try:
                ps = json.loads(ps_str)
                if ps:
                    first_trade_date = ps[0].get("d")
            except (ValueError, TypeError):
                pass

    return sp, txns, first_trade_date


def compute_flags(sp, txns, first_trade_date):
    flags = []
    sig_date = sp["signal_date"][:10]

    if not txns:
        flags.append("no_underlying_txns")
        return flags

    # 1. IPO proximity
    if first_trade_date:
        try:
            sd = datetime.strptime(sig_date, "%Y-%m-%d")
            fd = datetime.strptime(first_trade_date, "%Y-%m-%d")
            if 0 <= (fd - sd).days <= 7 or 0 <= (sd - fd).days <= 7:
                flags.append("IPO_proximity")
        except ValueError:
            pass

    # 2. Whole-dollar prices
    prices = [float(t["price"]) for t in txns if t["price"] is not None]
    if prices and all(p == int(p) for p in prices):
        flags.append("all_whole_dollar_prices")

    # 3. Single price
    if prices and len(set(round(p, 2) for p in prices)) == 1:
        flags.append("single_price_cluster")

    # 4. Single day
    dates = set(t["txn_date"] for t in txns)
    if len(dates) == 1:
        flags.append("single_day_cluster")

    # 5. All filtered (no GENUINE in underlying)
    classifications = [t["cls"] for t in txns]
    if all(c == "FILTERED" for c in classifications):
        flags.append("all_filtered")
    elif not any(c == "GENUINE" for c in classifications):
        flags.append("no_genuine_txns")

    # 6. Below threshold
    total_val = sum(abs(t["value"]) for t in txns if t["value"])
    if total_val < 100_000:
        flags.append("below_threshold")

    # 7. Tiny insiders
    distinct_insiders = set(t["insider"] for t in txns)
    if len(distinct_insiders) < 2:
        flags.append("tiny_insiders_count")

    # 8. Classification drift (num_insiders stored != actual)
    actual_n = len(distinct_insiders)
    stored_n = sp["num_insiders"] or 0
    if stored_n != actual_n:
        flags.append(f"insider_count_drift(stored={stored_n}_actual={actual_n})")

    return flags


def render_card(idx, total, sp, txns, first_trade_date, flags):
    sig_date = sp["signal_date"][:10]
    actionable = (sp.get("actionable_date") or sp["signal_date"])[:10]
    ret = sp.get("return_day0")
    alpha = (ret or 0) - (sp.get("spy_return_90d") or 0)
    mcap = (sp.get("market_cap") or 0) / 1e9

    lines = []
    flag_badge = "✅ CLEAN" if not flags else f"⚠️  {len(flags)} flags"
    lines.append(f"### [{idx}/{total}] {sp['ticker']} — {sp['company_name']}  {flag_badge}")
    lines.append(
        f"- signal_date: {sig_date}  (actionable: {actionable})  age: {sp.get('age_days') or '?'}d  "
        f"mature: {'Y' if sp.get('is_mature') else 'N'}"
    )
    lines.append(
        f"- stored: {sp.get('num_insiders')} insiders, "
        f"${(sp.get('total_value') or 0):,.0f} cluster, "
        f"${mcap:.2f}B mcap"
    )
    lines.append(
        f"- return_day0: {ret}%  spy_90d: {sp.get('spy_return_90d')}%  alpha: {alpha:+.2f}pp"
    )
    if first_trade_date:
        lines.append(f"- first_trade_day: {first_trade_date}")
    if flags:
        lines.append(f"- **flags:** {', '.join(flags)}")
    lines.append("")
    lines.append(f"Underlying P-transactions in 30d window ({len(txns)}):")
    lines.append("")
    lines.append("| Date | Insider | Title | Shares | Price | Value | Class | Accession |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for t in txns[:20]:
        title = (t.get("title") or "")[:30]
        insider = (t.get("insider") or "")[:25]
        shares = t.get("shares") or 0
        price = t.get("price") or 0
        value = t.get("value") or 0
        cls = t.get("cls") or "—"
        acc = t.get("acc") or "—"
        lines.append(
            f"| {t['txn_date']} | {insider} | {title} | {shares:,.0f} | ${price:g} | ${value:,.0f} | {cls} | {acc} |"
        )
    if len(txns) > 20:
        lines.append(f"| ... | (and {len(txns) - 20} more rows) | | | | | | |")
    lines.append("")
    # SEC links for the first few
    lines.append("SEC Form 4 links (first 3 distinct insiders):")
    seen = set()
    for t in txns:
        if t["insider"] in seen:
            continue
        seen.add(t["insider"])
        if len(seen) > 3:
            break
        acc = (t.get("acc") or "").replace("-", "")
        pd = t.get("primary_doc") or ""
        if acc and pd:
            url = f"https://www.sec.gov/Archives/edgar/data/{sp['cik'].lstrip('0')}/{acc}/{pd}"
        elif acc:
            url = f"https://www.sec.gov/Archives/edgar/data/{sp['cik'].lstrip('0')}/{acc}/"
        else:
            url = "(no accession)"
        lines.append(f"- [{t['insider']}]({url})")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="limit the output to N signals (sorted by flag count desc)")
    ap.add_argument("--out", default="signal_audit_2026-04-22.md")
    args = ap.parse_args()

    await Neo4jClient.connect()

    signals = await Neo4jClient.execute_query("""
        MATCH (sp:SignalPerformance)
        WHERE sp.is_mature = true AND sp.conviction_tier = 'strong_buy'
        RETURN sp.signal_id AS signal_id, sp.ticker AS ticker, sp.cik AS cik,
               sp.company_name AS company_name, sp.signal_date AS signal_date,
               sp.actionable_date AS actionable_date, sp.num_insiders AS num_insiders,
               sp.total_value AS total_value, sp.market_cap AS market_cap,
               sp.return_day0 AS return_day0, sp.spy_return_90d AS spy_return_90d,
               sp.is_mature AS is_mature, sp.age_days AS age_days
        ORDER BY sp.signal_date DESC
    """)
    print(f"Loaded {len(signals)} mature strong_buy signals")

    cards = []
    for sp_row in signals:
        sp, txns, first_trade = await load_signal_and_txns(sp_row)
        flags = compute_flags(sp, txns, first_trade)
        cards.append((len(flags), sp, txns, first_trade, flags))

    # Sort by flag count desc, then by signal_date desc
    cards.sort(key=lambda c: (-c[0], c[1]["signal_date"]), reverse=False)
    cards.sort(key=lambda c: c[0], reverse=True)

    to_write = cards[:args.limit] if args.limit else cards

    with open(args.out, "w") as f:
        f.write(f"# Signal Audit — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Scope: {len(signals)} mature strong_buy signals\n")
        f.write(f"Showing: {len(to_write)} (sorted by flag count desc)\n\n")

        flag_counter = {}
        for n_flags, sp, txns, ft, flags in cards:
            for flag in flags:
                fname = flag.split("(")[0]
                flag_counter[fname] = flag_counter.get(fname, 0) + 1
        f.write("## Flag prevalence across all 142\n\n")
        for fn, cnt in sorted(flag_counter.items(), key=lambda x: -x[1]):
            f.write(f"- `{fn}`: {cnt}\n")
        f.write("\n---\n\n")

        for idx, (n_flags, sp, txns, ft, flags) in enumerate(to_write, 1):
            f.write(render_card(idx, len(to_write), sp, txns, ft, flags))

    print(f"Wrote: {args.out}")
    print(f"Flag prevalence across 142 mature signals:")
    for fn, cnt in sorted(flag_counter.items(), key=lambda x: -x[1]):
        print(f"  {fn}: {cnt}")

    await Neo4jClient.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
