// ============================================
// Corporate Intelligence Graph - Neo4j Constraints
// ============================================
// Run these constraints before importing data to ensure data integrity

// Company constraints
CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT company_cik_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.cik IS UNIQUE;

CREATE CONSTRAINT company_lei_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.lei IS UNIQUE;

// Person constraints
CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.id IS UNIQUE;

// Address constraints
CREATE CONSTRAINT address_id_unique IF NOT EXISTS
FOR (a:Address) REQUIRE a.id IS UNIQUE;

// Filing constraints
CREATE CONSTRAINT filing_id_unique IF NOT EXISTS
FOR (f:Filing) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT filing_accession_unique IF NOT EXISTS
FOR (f:Filing) REQUIRE f.accession_number IS UNIQUE;

// Jurisdiction constraints
CREATE CONSTRAINT jurisdiction_code_unique IF NOT EXISTS
FOR (j:Jurisdiction) REQUIRE j.code IS UNIQUE;

// InsiderTransaction constraints
CREATE CONSTRAINT insider_txn_id_unique IF NOT EXISTS
FOR (t:InsiderTransaction) REQUIRE t.id IS UNIQUE;

// Note: Removed composite node key constraint (normalized_name, jurisdiction)
// as companies may not always have jurisdiction information
