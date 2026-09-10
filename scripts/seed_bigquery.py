"""Seed script: 6 banks, 3 snapshots each (18 total) with diverse states."""
from __future__ import annotations
import logging, uuid
from datetime import date as dt_date, datetime, timezone
from investiq.models.company import CompanyProfile, CompanyType, Sector
from investiq.models.evidence import EvidenceDomain, EvidenceItem, EvidenceTag
from investiq.models.financials import FinancialData, MarketData
from investiq.models.metrics import BankMetrics
from investiq.models.research import FindingCategory, ResearchFinding, ResearchSnapshot
from investiq.models.synthesis import CIOSynthesis
from investiq.models.valuation import ValuationMethod, ValuationResult, ValuationSummary
from investiq.storage.bigquery import BigQueryResearchRepository
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BANKS = [
    {"ticker":"HDFCBANK","name":"HDFC Bank Limited","sub":"Private Sector Bank",
     "p":[1880,1925,1970],"fv":[2100,2180,2250],
     "v":["Undervalued","Undervalued","Undervalued"],
     "a":["Conviction Buy","Conviction Buy","Conviction Buy"],"trend":"improving",
     "m":{"roe":[15.0,15.8,16.5],"roa":[1.50,1.60,1.70],"nim":[3.5,3.6,3.7],
          "casa":[35.0,36.0,37.0],"cti":[45.0,43.5,42.0],
          "gnpa":[1.20,1.10,1.00],"nnpa":[0.40,0.30,0.25],"cc":[0.50,0.45,0.40],
          "eps":[80,86,92],"bv":[500,530,560]}},
    {"ticker":"ICICIBANK","name":"ICICI Bank Limited","sub":"Private Sector Bank",
     "p":[1420,1580,1720],"fv":[1550,1620,1650],
     "v":["Undervalued","Fairly Valued","Overvalued"],
     "a":["Buy","Cautious","Hold"],"trend":"compressing",
     "m":{"roe":[14.0,14.5,14.8],"roa":[1.40,1.45,1.48],"nim":[3.8,3.9,4.0],
          "casa":[38.0,39.0,40.0],"cti":[42.0,41.0,40.0],
          "gnpa":[1.50,1.40,1.30],"nnpa":[0.50,0.45,0.40],"cc":[0.60,0.55,0.50],
          "eps":[55,62,68],"bv":[380,410,430]}},
    {"ticker":"SBIN","name":"State Bank of India","sub":"Public Sector Bank",
     "p":[790,740,700],"fv":[850,750,610],
     "v":["Undervalued","Fairly Valued","Overvalued"],
     "a":["Buy","Cautious","Avoid"],"trend":"declining",
     "m":{"roe":[12.5,11.8,10.5],"roa":[0.90,0.82,0.72],"nim":[3.0,2.9,2.7],
          "casa":[41.0,40.0,38.0],"cti":[48.0,49.5,52.0],
          "gnpa":[2.50,2.80,3.50],"nnpa":[0.80,0.95,1.20],"cc":[1.00,1.15,1.40],
          "eps":[45,42,36],"bv":[300,310,305]}},
    {"ticker":"BANDHANBNK","name":"Bandhan Bank Limited","sub":"Private Sector Bank",
     "p":[155,168,185],"fv":[165,175,200],
     "v":["Fairly Valued","Fairly Valued","Undervalued"],
     "a":["Cautious","Cautious","Buy"],"trend":"turnaround",
     "m":{"roe":[9.5,10.5,12.5],"roa":[1.05,1.15,1.35],"nim":[4.2,4.3,4.4],
          "casa":[32.0,33.0,34.5],"cti":[46.5,45.5,44.0],
          "gnpa":[4.20,3.80,3.00],"nnpa":[1.50,1.30,1.00],"cc":[1.80,1.60,1.30],
          "eps":[10.5,12.0,14.5],"bv":[105,112,122]}},
    {"ticker":"RBLBANK","name":"RBL Bank Limited","sub":"Private Sector Bank",
     "p":[245,250,260],"fv":[220,235,255],
     "v":["Overvalued","Fairly Valued","Fairly Valued"],
     "a":["Avoid","Cautious","Cautious"],"trend":"mixed",
     "m":{"roe":[9.0,9.5,10.0],"roa":[0.80,0.85,0.90],"nim":[3.5,3.6,3.6],
          "casa":[30.0,30.5,31.0],"cti":[50.0,49.0,48.5],
          "gnpa":[4.00,3.80,3.60],"nnpa":[1.50,1.45,1.40],"cc":[1.80,1.75,1.70],
          "eps":[18,19,20],"bv":[160,165,172]}},
    {"ticker":"FEDERALBNK","name":"Federal Bank Limited","sub":"Private Sector Bank",
     "p":[205,210,215],"fv":[200,208,215],
     "v":["Fairly Valued","Fairly Valued","Fairly Valued"],
     "a":["Hold","Hold","Hold"],"trend":"stable",
     "m":{"roe":[12.0,12.2,12.3],"roa":[1.00,1.02,1.03],"nim":[3.2,3.2,3.3],
          "casa":[33.0,33.5,33.5],"cti":[47.0,46.5,46.5],
          "gnpa":[2.20,2.10,2.10],"nnpa":[0.70,0.68,0.65],"cc":[1.20,1.18,1.15],
          "eps":[14,14.5,15],"bv":[140,144,148]}},
]


def sid(prefix, i):
    return "syn-"+prefix.lower()+"-r"+str(i+1)+"-"+uuid.uuid4().hex[:8]

_F = {}
_F["improving"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Strengthening Profitability",
        statement=f"ROE {lm.roe}%, NIM {lm.nim}% with sustained momentum.",confidence=0.88,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Core profitability improving.",positive_implication="Above-peer margins."),
    ResearchFinding(analyst="asset_quality_analyst",title="Controlled Asset Quality",
        statement=f"GNPA {lm.gross_npa_ratio}% with declining trend.",confidence=0.85,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="Reducing NPAs lower burden.",positive_implication="Improving asset quality."),
    ResearchFinding(analyst="banking_business_analyst",title="Strengthening Deposit Franchise",
        statement=f"CASA {lm.casa_ratio}% provides low-cost edge.",confidence=0.90,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Low-cost deposits sustain NIM.",positive_implication="Stable funding base.")]
_F["compressing"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Solid But Getting Pricey",
        statement=f"ROE {lm.roe}%, NIM {lm.nim}% healthy but valuation expanded.",confidence=0.82,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Valuation compression risk.",negative_implication="Price exceeds fair value."),
    ResearchFinding(analyst="asset_quality_analyst",title="Healthy Asset Quality",
        statement=f"GNPA {lm.gross_npa_ratio}% controlled.",confidence=0.83,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="Low NPAs ensure stability.",positive_implication="Adequate coverage."),
    ResearchFinding(analyst="banking_business_analyst",title="Strong Franchise, Fairly Priced",
        statement=f"CASA {lm.casa_ratio}% strength priced in.",confidence=0.80,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Good business, less safety margin.",negative_implication="Upside limited.")]
_F["declining"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Deteriorating Profitability",
        statement=f"ROE {lm.roe}% declining; cost-income {lm.cost_to_income}% rising.",confidence=0.78,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Core earnings weakening.",negative_implication="Margins under pressure."),
    ResearchFinding(analyst="asset_quality_analyst",title="Elevated AQ Stress",
        statement=f"GNPA {lm.gross_npa_ratio}% rising with higher credit costs.",confidence=0.75,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="Rising NPAs increase provisions.",negative_implication="Credit costs weighing."),
    ResearchFinding(analyst="banking_business_analyst",title="Weakening Franchise",
        statement=f"CASA {lm.casa_ratio}% declining, funding costs rising.",confidence=0.72,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Higher funding costs compress NIM.",negative_implication="Competition erodes base.")]

_F["turnaround"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Improving From Low Base",
        statement=f"ROE recovering to {lm.roe}%; NIM {lm.nim}% stable.",confidence=0.80,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Turnaround gaining traction.",positive_implication="Low base offers room."),
    ResearchFinding(analyst="asset_quality_analyst",title="AQ Improving",
        statement=f"GNPA {lm.gross_npa_ratio}% down from elevated levels.",confidence=0.82,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="Provision relief from AQ recovery.",positive_implication="Stressed asset recovery."),
    ResearchFinding(analyst="banking_business_analyst",title="Franchise Rebuilding",
        statement=f"CASA {lm.casa_ratio}% improving as confidence returns.",confidence=0.78,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Better deposit mix supports NIM.",positive_implication="Stabilizing funding.")]
_F["mixed"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Modest Profit Improvement",
        statement=f"ROE {lm.roe}%, NIM {lm.nim}% gradual but below peers.",confidence=0.75,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Improving from weak base.",negative_implication="Below-peer margins."),
    ResearchFinding(analyst="asset_quality_analyst",title="Persistent AQ Weakness",
        statement=f"GNPA {lm.gross_npa_ratio}% elevated, slow improvement.",confidence=0.70,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="High NPAs drag earnings.",negative_implication="Provisions consume profit."),
    ResearchFinding(analyst="banking_business_analyst",title="Narrow Franchise Moat",
        statement=f"CASA {lm.casa_ratio}% limits low-cost advantage.",confidence=0.72,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Limited deposit franchise.",negative_implication="Higher wholesale funding reliance.")]
_F["stable"] = lambda t,lm: [
    ResearchFinding(analyst="financial_analyst",title="Consistent Profitability",
        statement=f"ROE {lm.roe}%, NIM {lm.nim}% stable.",confidence=0.85,
        evidence_ids=[f"SYN-{t}-ROE-001",f"SYN-{t}-NIM-001"],category=FindingCategory.PROFITABILITY,
        why_it_matters="Reliable earnings.",positive_implication="Predictable returns."),
    ResearchFinding(analyst="asset_quality_analyst",title="Stable AQ",
        statement=f"GNPA {lm.gross_npa_ratio}% consistent.",confidence=0.85,
        evidence_ids=[f"SYN-{t}-AQ-001"],category=FindingCategory.ASSET_QUALITY,
        why_it_matters="Controlled NPAs provide stability.",positive_implication="No surprise provisions."),
    ResearchFinding(analyst="banking_business_analyst",title="Steady Franchise",
        statement=f"CASA {lm.casa_ratio}% supports NIM.",confidence=0.87,
        evidence_ids=[f"SYN-{t}-CASA-001"],category=FindingCategory.LIABILITY_FRANCHISE,
        why_it_matters="Stable deposit base is defensive.",positive_implication="Consistent low-cost funding.")]

_C = {}
_C["improving"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" shows strong fundamentals with improving profitability.",
    investment_thesis="Improving trend supports positive outlook.",
    key_strengths=["Industry positioning","Consistent improvement","Sound asset quality"],
    key_concerns=["Macro headwinds","Regulatory environment"],
    growth_drivers=["Digital banking","Retail lending"],risks=["Rate volatility","Regulatory changes"],
    bull_case="Continued momentum drives earnings growth.",
    base_case="Stable environment supports steady performance.",
    bear_case="Macro stress could slow improvements.",
    thesis_breakers=["Sustained AQ deterioration"],overall_assessment=a)
_C["compressing"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" has solid fundamentals but price ran ahead of FV.",
    investment_thesis="Strong franchise with diminishing upside.",
    key_strengths=["Market position","Solid profitability","Healthy AQ"],
    key_concerns=["Valuation compression","Limited upside","High expectations"],
    growth_drivers=["Digital adoption","Fee income"],risks=["Price correction","Rate cycle"],
    bull_case="Earnings growth catches price.",base_case="Stable earnings, modest appreciation.",
    bear_case="Multiple contraction on disappointment.",
    thesis_breakers=["Sharp earnings downgrade"],overall_assessment=a)
_C["declining"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" faces declining profitability and rising AQ stress.",
    investment_thesis="Avoid until stabilization signs appear.",
    key_strengths=["Large branch network","Government backing"],
    key_concerns=["Declining ROE","Rising NPAs","Margin compression"],
    growth_drivers=["Cost restructuring","Digital transformation"],
    risks=["Further AQ deterioration","Earnings downgrade"],
    bull_case="Restructuring reverses decline.",base_case="Continued pressure, gradual stabilization.",
    bear_case="Further deterioration, earnings shock.",
    thesis_breakers=["ROE stabilization","NPA trend reversal"],overall_assessment=a)
_C["turnaround"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" is executing a turnaround with improving profitability.",
    investment_thesis="Turnaround with improving AQ offers upside.",
    key_strengths=["Improving profitability","AQ recovery","Franchise rebuilding"],
    key_concerns=["NPAs still above peers","Execution risk"],
    growth_drivers=["Turnaround execution","Market share recovery"],
    risks=["Turnaround stalls","Macro headwinds"],
    bull_case="Successful turnaround to peer profitability.",
    base_case="Gradual improvement with setbacks.",
    bear_case="Turnaround fails, requiring capital.",
    thesis_breakers=["Sustained earnings recovery 3+ quarters"],overall_assessment=a)
_C["mixed"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" presents mixed signals -- modest improvements, weak AQ.",
    investment_thesis="Mixed signals warrant caution.",
    key_strengths=["Modest profit improvement","Some NPA reduction"],
    key_concerns=["Elevated AQ stress","Narrow franchise","Below-peer margins"],
    growth_drivers=["Digital banking","Retail lending"],risks=["AQ deterioration","Funding cost pressure"],
    bull_case="AQ improvement accelerates.",base_case="Gradual improvement in select metrics.",
    bear_case="AQ stress persists, delaying turnaround.",
    thesis_breakers=["GNPA below 3% sustained"],overall_assessment=a)
_C["stable"] = lambda n,a: CIOSynthesis(
    executive_summary=n+" delivers consistent, predictable performance.",
    investment_thesis="Reliable for steady returns, limited catalysts.",
    key_strengths=["Stable profitability","Controlled AQ","Reliable franchise"],
    key_concerns=["Limited growth catalysts","No re-rating trigger"],
    growth_drivers=["Digital enhancements","Fee income"],risks=["Competitive pressure","Rate cycle"],
    bull_case="Earnings growth drives re-rating.",base_case="Stable performance at fair valuation.",
    bear_case="Margin compression from competition.",
    thesis_breakers=["Significant metric deviation"],overall_assessment=a)

def snap(bank, i, dates):
    t=bank["ticker"]; m=bank["m"]; fy=["FY2024","FY2025","FY2026"]
    price=bank["p"][i]; fv=bank["fv"][i]
    company=CompanyProfile(ticker=t,name=bank["name"],sector=Sector.FINANCIAL_SERVICES,
        company_type=CompanyType.BANK,sub_sector=bank["sub"])
    gen=datetime.combine(dates[i],datetime.min.time(),tzinfo=timezone.utc)
    sid_=sid(t,i)
    metrics=[BankMetrics(fiscal_year=fy[j],roe=m["roe"][j],roa=m["roa"][j],
        nim=m["nim"][j],casa_ratio=m["casa"][j],cost_to_income=m["cti"][j],
        gross_npa_ratio=m["gnpa"][j],net_npa_ratio=m["nnpa"][j],
        credit_cost=m["cc"][j],eps=m["eps"][j],book_value_per_share=m["bv"][j],
        evidence=[]) for j in range(3)]
    lm=metrics[-1]
    upside=round(((fv-price)/price)*100,1)
    valuation=ValuationSummary(methods=[ValuationResult(method=ValuationMethod.PB_ROE,
        estimated_fair_value=fv,current_price=price,upside_pct=upside,assumptions=[],evidence=[])],
        blended_fair_value=fv,verdict=bank["v"][i])
    ev=[EvidenceItem(evidence_id=f"SYN-{t}-ROE-001",tag=EvidenceTag.CALCULATION,
        label=f"ROE {lm.roe}%",source=f"{bank['name']} Financial Stmts FY2026",
        source_field="metrics.roe",publication_date=dt_date(2026,6,30),value=lm.roe,
        domain=EvidenceDomain.FINANCIAL),EvidenceItem(evidence_id=f"SYN-{t}-NIM-001",
        tag=EvidenceTag.CALCULATION,label=f"NIM {lm.nim}%",source=f"{bank['name']} Financial Stmts FY2026",
        source_field="metrics.nim",publication_date=dt_date(2026,6,30),value=lm.nim,
        domain=EvidenceDomain.FINANCIAL),EvidenceItem(evidence_id=f"SYN-{t}-CASA-001",
        tag=EvidenceTag.CALCULATION,label=f"CASA {lm.casa_ratio}%",source=f"{bank['name']} Financial Stmts FY2026",
        source_field="metrics.casa_ratio",publication_date=dt_date(2026,6,30),value=lm.casa_ratio,
        domain=EvidenceDomain.FINANCIAL),EvidenceItem(evidence_id=f"SYN-{t}-AQ-001",
        tag=EvidenceTag.CALCULATION,label=f"GNPA {lm.gross_npa_ratio}%",source=f"{bank['name']} Financial Stmts FY2026",
        source_field="metrics.gross_npa_ratio",publication_date=dt_date(2026,6,30),
        value=lm.gross_npa_ratio,domain=EvidenceDomain.ASSET_QUALITY)]
    findings=_F.get(bank["trend"],_F["stable"])(t,lm)
    cio=_C.get(bank["trend"],_C["stable"])(bank["name"],bank["a"][i])
    fd=FinancialData(company=company,income_statements=[],balance_sheets=[],
        market_data=MarketData(current_price=price,market_cap=price*100,
            shares_outstanding=100.0,as_of=dates[i]))
    return ResearchSnapshot(snapshot_id=sid_,ticker=t,company=company,
        generated_at=gen,financial_data=fd,metrics=metrics,valuation=valuation,
        findings=findings,evidence_chain=ev,cio_synthesis=cio)

def main():
    repo=BigQueryResearchRepository()
    c=repo.client; ds=repo.dataset_id; pr=c.project
    tables=[repo.TABLE_SNAPSHOTS,repo.TABLE_METRICS,repo.TABLE_FINDINGS,
            repo.TABLE_EVIDENCE,repo.TABLE_SCENARIOS,repo.TABLE_THESIS_ITEMS]
    logger.info("Cleaning existing data...")
    for tbl in tables:
        c.query("DELETE FROM `"+pr+"."+ds+"."+tbl+"` WHERE TRUE").result()
        logger.info("  Cleared %s",tbl)
    dates=[dt_date(2026,8,20),dt_date(2026,8,29),dt_date(2026,9,8)]
    total=0
    for bank in BANKS:
        for i in range(3):
            repo.save_snapshot(snap(bank,i,dates))
            total+=1
            logger.info("  Saved %s snap %d/3",bank["ticker"],i+1)
    logger.info("")
    logger.info("=== Verification ===")
    for tbl in tables:
        q=c.query("SELECT COUNT(*) as c FROM `"+pr+"."+ds+"."+tbl+"`").result()
        logger.info("  %s: %d rows",tbl,list(q)[0]["c"])
    logger.info("Done -- %d snapshots, %d banks.",total,len(BANKS))

if __name__=="__main__":
    main()
