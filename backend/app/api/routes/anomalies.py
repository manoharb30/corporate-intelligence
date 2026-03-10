"""Insider-Event Anomaly API — surfaces front-loaded selling before 8-K events."""

from fastapi import APIRouter, Query

from app.db.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/top")
async def get_top_anomalies(limit: int = Query(15, ge=1, le=100)):
    """
    Return top front-loaded insider selling anomalies.

    Finds company-event pairs where insiders sold heavily BEFORE material
    8-K events (ratio > 0.8, total value > $1M). Excludes treasury
    transactions. Sorted by pre-event selling value descending.
    """
    query = """
        MATCH (c:Company)-[:FILED_EVENT]->(e:Event)
        MATCH (c)-[:INSIDER_TRADE_OF]->(t:InsiderTransaction)
        WHERE t.transaction_code IN ['P', 'S']
          AND toLower(t.insider_name) <> toLower(c.name)
        WITH c, e, t,
             date(substring(e.filing_date, 0, 10)) AS event_dt,
             date(substring(t.transaction_date, 0, 10)) AS txn_dt
        WHERE txn_dt >= event_dt - duration({days: 30})
          AND txn_dt <= event_dt + duration({days: 30})
        WITH c, e, event_dt,
             sum(CASE WHEN t.transaction_code = 'S' AND txn_dt < event_dt
                 THEN coalesce(t.total_value, 0) ELSE 0 END) AS sell_before,
             sum(CASE WHEN t.transaction_code = 'S' AND txn_dt >= event_dt
                 THEN coalesce(t.total_value, 0) ELSE 0 END) AS sell_after,
             collect(DISTINCT CASE WHEN t.transaction_code = 'S' AND txn_dt < event_dt
                 THEN t.insider_name + CASE WHEN t.insider_title IS NOT NULL
                 AND t.insider_title <> '' THEN ' (' + t.insider_title + ')'
                 ELSE '' END END) AS pre_insider_details,
             collect(CASE WHEN t.transaction_code = 'S' AND txn_dt < event_dt
                 THEN duration.inDays(txn_dt, event_dt).days END) AS days_list
        WITH c, e, event_dt, sell_before, sell_after, pre_insider_details,
             days_list,
             sell_before + sell_after AS total_sell
        WHERE total_sell >= 1000000
        WITH c, e, event_dt, sell_before, sell_after, total_sell,
             [d IN days_list WHERE d IS NOT NULL] AS clean_days,
             CASE WHEN total_sell > 0 THEN sell_before * 1.0 / total_sell
             ELSE 0 END AS frontload_ratio,
             [x IN pre_insider_details WHERE x IS NOT NULL] AS insiders
        WHERE frontload_ratio > 0.8
        RETURN c.cik AS cik,
               c.name AS company_name,
               c.tickers AS tickers,
               e.signal_type AS signal_type,
               toString(event_dt) AS event_date,
               e.accession_number AS accession_number,
               sell_before,
               sell_after,
               total_sell,
               frontload_ratio,
               size(insiders) AS num_insiders,
               insiders,
               clean_days
        ORDER BY sell_before DESC
        LIMIT $raw_limit
    """
    # Fetch more than needed to account for dedup/filtering
    results = await Neo4jClient.execute_query(query, {"raw_limit": limit * 10})

    # Deduplicate: keep only the highest-value row per company
    seen_companies = set()
    anomalies = []

    for r in results:
        company_key = r["cik"]
        if company_key in seen_companies:
            continue
        seen_companies.add(company_key)

        tickers = r["tickers"]
        ticker = tickers[0] if tickers and isinstance(tickers, list) else None

        # Skip PE lockup (Medline — known IPO context)
        if ticker == "MDLN":
            continue

        # Calculate avg days before event from the days list
        clean_days = r.get("clean_days") or []
        avg_days = (
            round(sum(clean_days) / len(clean_days), 1)
            if clean_days
            else None
        )

        # Construct EDGAR filing URL from accession number + CIK
        acc = r["accession_number"] or ""
        cik_clean = r["cik"].lstrip("0") if r["cik"] else ""
        acc_nodash = acc.replace("-", "")
        edgar_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{acc_nodash}/{acc}-index.htm"
            if acc and cik_clean
            else None
        )

        anomalies.append({
            "cik": r["cik"],
            "company_name": r["company_name"],
            "ticker": ticker,
            "event_type": r["signal_type"],
            "event_date": r["event_date"],
            "accession_number": r["accession_number"],
            "edgar_url": edgar_url,
            "num_insiders": r["num_insiders"],
            "insider_names_and_titles": r["insiders"],
            "pre_event_sell_value": round(r["sell_before"], 2),
            "post_event_sell_value": round(r["sell_after"], 2),
            "ratio": round(r["frontload_ratio"], 4),
            "total_value": round(r["total_sell"], 2),
            "avg_days_before_event": avg_days,
        })

    return {"total": len(anomalies), "anomalies": anomalies[:limit]}


@router.get("/download")
async def download_anomalies_csv():
    """Return the full anomaly CSV file for download."""
    import os
    from fastapi.responses import FileResponse

    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "lookinsight_insider_event_signals_v2.csv",
    )
    if not os.path.exists(csv_path):
        return {"error": "CSV file not found"}

    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="lookinsight_insider_event_signals.csv",
    )
