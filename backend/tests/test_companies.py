"""Test companies for SEC EDGAR pipeline validation."""

# 10 test companies with known ownership data for validation
TEST_COMPANIES = [
    {
        "cik": "0000320193",
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
    },
    {
        "cik": "0000789019",
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "sector": "Technology",
    },
    {
        "cik": "0001018724",
        "ticker": "AMZN",
        "name": "Amazon.com Inc.",
        "sector": "Consumer Cyclical",
    },
    {
        "cik": "0001652044",
        "ticker": "GOOGL",
        "name": "Alphabet Inc.",
        "sector": "Technology",
    },
    {
        "cik": "0001326801",
        "ticker": "META",
        "name": "Meta Platforms Inc.",
        "sector": "Technology",
    },
    {
        "cik": "0001045810",
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "sector": "Technology",
    },
    {
        "cik": "0000051143",
        "ticker": "IBM",
        "name": "International Business Machines",
        "sector": "Technology",
    },
    {
        "cik": "0000078003",
        "ticker": "PFE",
        "name": "Pfizer Inc.",
        "sector": "Healthcare",
    },
    {
        "cik": "0000093410",
        "ticker": "CVX",
        "name": "Chevron Corporation",
        "sector": "Energy",
    },
    {
        "cik": "0000732717",
        "ticker": "BAC",
        "name": "Bank of America Corporation",
        "sector": "Financial Services",
    },
]

# Known facts for spot-checking extraction accuracy
KNOWN_FACTS = {
    "0000320193": {  # Apple
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "expected_officers": ["Tim Cook", "Luca Maestri", "Jeff Williams", "Katherine Adams"],
        "expected_major_holders": ["Vanguard", "BlackRock", "Berkshire Hathaway"],
        "subsidiary_count_min": 30,
        "state_of_incorporation": "California",
    },
    "0000789019": {  # Microsoft
        "name": "Microsoft Corporation",
        "ticker": "MSFT",
        "expected_officers": ["Satya Nadella", "Amy Hood", "Brad Smith"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 100,
        "state_of_incorporation": "Washington",
    },
    "0001018724": {  # Amazon
        "name": "Amazon.com Inc.",
        "ticker": "AMZN",
        "expected_officers": ["Andy Jassy", "Brian Olsavsky"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 50,
        "state_of_incorporation": "Delaware",
    },
    "0001652044": {  # Alphabet
        "name": "Alphabet Inc.",
        "ticker": "GOOGL",
        "expected_officers": ["Sundar Pichai", "Ruth Porat"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 100,
        "state_of_incorporation": "Delaware",
    },
    "0001326801": {  # Meta
        "name": "Meta Platforms Inc.",
        "ticker": "META",
        "expected_officers": ["Mark Zuckerberg", "Susan Li"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 50,
        "state_of_incorporation": "Delaware",
    },
    "0001045810": {  # NVIDIA
        "name": "NVIDIA Corporation",
        "ticker": "NVDA",
        "expected_officers": ["Jensen Huang", "Colette Kress"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 20,
        "state_of_incorporation": "Delaware",
    },
    "0000051143": {  # IBM
        "name": "International Business Machines",
        "ticker": "IBM",
        "expected_officers": ["Arvind Krishna", "James Kavanaugh"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 100,
        "state_of_incorporation": "New York",
    },
    "0000078003": {  # Pfizer
        "name": "Pfizer Inc.",
        "ticker": "PFE",
        "expected_officers": ["Albert Bourla", "David Denton"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 50,
        "state_of_incorporation": "Delaware",
    },
    "0000093410": {  # Chevron
        "name": "Chevron Corporation",
        "ticker": "CVX",
        "expected_officers": ["Mike Wirth", "Pierre Breber"],
        "expected_major_holders": ["Vanguard", "BlackRock"],
        "subsidiary_count_min": 100,
        "state_of_incorporation": "Delaware",
    },
    "0000732717": {  # Bank of America
        "name": "Bank of America Corporation",
        "ticker": "BAC",
        "expected_officers": ["Brian Moynihan", "Alastair Borthwick"],
        "expected_major_holders": ["Vanguard", "BlackRock", "Berkshire Hathaway"],
        "subsidiary_count_min": 100,
        "state_of_incorporation": "Delaware",
    },
}


def get_test_ciks() -> list[str]:
    """Get list of CIKs for test companies."""
    return [c["cik"] for c in TEST_COMPANIES]


def get_company_by_ticker(ticker: str) -> dict | None:
    """Get company info by ticker symbol."""
    for company in TEST_COMPANIES:
        if company["ticker"] == ticker:
            return company
    return None


def get_known_facts(cik: str) -> dict | None:
    """Get known facts for a company by CIK."""
    return KNOWN_FACTS.get(cik)
