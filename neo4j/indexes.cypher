// ============================================
// Corporate Intelligence Graph - Neo4j Indexes
// ============================================
// Run these indexes after constraints to optimize query performance

// Company indexes
CREATE INDEX company_name_idx IF NOT EXISTS
FOR (c:Company) ON (c.name);

CREATE INDEX company_normalized_name_idx IF NOT EXISTS
FOR (c:Company) ON (c.normalized_name);

CREATE INDEX company_cik_idx IF NOT EXISTS
FOR (c:Company) ON (c.cik);

CREATE INDEX company_lei_idx IF NOT EXISTS
FOR (c:Company) ON (c.lei);

CREATE INDEX company_jurisdiction_idx IF NOT EXISTS
FOR (c:Company) ON (c.jurisdiction);

CREATE INDEX company_status_idx IF NOT EXISTS
FOR (c:Company) ON (c.status);

// Person indexes
CREATE INDEX person_name_idx IF NOT EXISTS
FOR (p:Person) ON (p.name);

CREATE INDEX person_normalized_name_idx IF NOT EXISTS
FOR (p:Person) ON (p.normalized_name);

CREATE INDEX person_pep_idx IF NOT EXISTS
FOR (p:Person) ON (p.is_pep);

CREATE INDEX person_sanctioned_idx IF NOT EXISTS
FOR (p:Person) ON (p.is_sanctioned);

// Address indexes
CREATE INDEX address_country_idx IF NOT EXISTS
FOR (a:Address) ON (a.country);

CREATE INDEX address_city_idx IF NOT EXISTS
FOR (a:Address) ON (a.city);

CREATE INDEX address_state_idx IF NOT EXISTS
FOR (a:Address) ON (a.state);

CREATE INDEX address_entity_count_idx IF NOT EXISTS
FOR (a:Address) ON (a.entity_count);

// Full-text search index for addresses
CREATE FULLTEXT INDEX address_fulltext_idx IF NOT EXISTS
FOR (a:Address) ON EACH [a.full_address];

// Filing indexes
CREATE INDEX filing_form_type_idx IF NOT EXISTS
FOR (f:Filing) ON (f.form_type);

CREATE INDEX filing_date_idx IF NOT EXISTS
FOR (f:Filing) ON (f.filing_date);

CREATE INDEX filing_accession_idx IF NOT EXISTS
FOR (f:Filing) ON (f.accession_number);

// Jurisdiction indexes
CREATE INDEX jurisdiction_country_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.country);

CREATE INDEX jurisdiction_secrecy_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.is_secrecy_jurisdiction);

CREATE INDEX jurisdiction_secrecy_score_idx IF NOT EXISTS
FOR (j:Jurisdiction) ON (j.secrecy_score);

// Full-text search indexes for entity name matching
CREATE FULLTEXT INDEX company_name_fulltext_idx IF NOT EXISTS
FOR (c:Company) ON EACH [c.name, c.normalized_name];

CREATE FULLTEXT INDEX person_name_fulltext_idx IF NOT EXISTS
FOR (p:Person) ON EACH [p.name, p.normalized_name];

// Relationship property indexes for ownership queries
CREATE INDEX owns_percentage_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.percentage);

CREATE INDEX owns_beneficial_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.is_beneficial);

CREATE INDEX same_as_confidence_idx IF NOT EXISTS
FOR ()-[r:SAME_AS]-() ON (r.confidence);

// ============================================
// Citation and Provenance Indexes
// ============================================

// Filing URL index for citation lookups
CREATE INDEX filing_url_idx IF NOT EXISTS
FOR (f:Filing) ON (f.filing_url);

// Filing extraction method for filtering
CREATE INDEX filing_extraction_method_idx IF NOT EXISTS
FOR (f:Filing) ON (f.extraction_method);

// Relationship source_filing indexes for citation tracing
CREATE INDEX owns_source_filing_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.source_filing);

CREATE INDEX owns_confidence_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.confidence);

CREATE INDEX officer_of_source_filing_idx IF NOT EXISTS
FOR ()-[r:OFFICER_OF]-() ON (r.source_filing);

CREATE INDEX officer_of_confidence_idx IF NOT EXISTS
FOR ()-[r:OFFICER_OF]-() ON (r.confidence);

CREATE INDEX director_of_source_filing_idx IF NOT EXISTS
FOR ()-[r:DIRECTOR_OF]-() ON (r.source_filing);

CREATE INDEX director_of_confidence_idx IF NOT EXISTS
FOR ()-[r:DIRECTOR_OF]-() ON (r.confidence);

// InsiderTransaction indexes
CREATE INDEX insider_txn_date_idx IF NOT EXISTS
FOR (t:InsiderTransaction) ON (t.transaction_date);

CREATE INDEX insider_txn_code_idx IF NOT EXISTS
FOR (t:InsiderTransaction) ON (t.transaction_code);

CREATE INDEX insider_txn_filing_date_idx IF NOT EXISTS
FOR (t:InsiderTransaction) ON (t.filing_date);

CREATE INDEX insider_txn_accession_idx IF NOT EXISTS
FOR (t:InsiderTransaction) ON (t.accession_number);

// Extraction method indexes on relationships for filtering
CREATE INDEX owns_extraction_method_idx IF NOT EXISTS
FOR ()-[r:OWNS]-() ON (r.extraction_method);

CREATE INDEX officer_of_extraction_method_idx IF NOT EXISTS
FOR ()-[r:OFFICER_OF]-() ON (r.extraction_method);

CREATE INDEX director_of_extraction_method_idx IF NOT EXISTS
FOR ()-[r:DIRECTOR_OF]-() ON (r.extraction_method);
