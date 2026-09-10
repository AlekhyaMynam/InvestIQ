"""Verify seeded BigQuery data."""
from google.cloud import bigquery
c = bigquery.Client()
rows = list(c.query("""
    SELECT ticker, generated_at, current_price, blended_fair_value,
           valuation_verdict, overall_assessment
    FROM investiq-506107.investiq.research_snapshots
    ORDER BY ticker, generated_at
""").result())
print("=== Prices by ticker and date ===")
for r in rows:
    d = str(r["generated_at"])[:10]
    p = r["current_price"]
    fv = r["blended_fair_value"]
    print(f"  {r['ticker']:12s} {d:15s} price={p:>8.1f} fv={fv:>8.1f} verdict={r['valuation_verdict']}")

print()
print("=== Row counts ===")
for t in ["research_snapshots","research_metrics","research_findings",
           "research_evidence","research_scenarios","research_thesis_items"]:
    cnt = list(c.query(f"SELECT COUNT(*) as c FROM investiq-506107.investiq.{t}").result())[0]["c"]
    print(f"  {t}: {cnt} rows")