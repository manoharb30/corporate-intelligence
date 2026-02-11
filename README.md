# Corporate Intelligence Graph

A beneficial ownership intelligence platform built with Neo4j, FastAPI, and React.

## Overview

This platform enables analysis of corporate ownership structures, identifying beneficial owners, and detecting potential risk indicators such as:

- Complex ownership chains
- Circular ownership structures
- Connections to Politically Exposed Persons (PEPs)
- Connections to sanctioned individuals
- Entities in secrecy jurisdictions
- Suspicious address clustering

## Tech Stack

- **Database**: Neo4j (graph database)
- **Backend**: FastAPI + Python
- **Validation**: Pydantic
- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **LLM**: Anthropic Claude API (for structured extraction)

## Project Structure

```
corporate-intelligence-graph/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Application settings
│   │   ├── api/routes/          # API endpoints
│   │   ├── models/              # Pydantic models
│   │   ├── services/            # Business logic
│   │   └── db/
│   │       └── neo4j_client.py  # Neo4j connection
│   ├── ingestion/
│   │   ├── sec_edgar/           # SEC EDGAR data fetchers
│   │   └── common/              # Shared parsing utilities
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Page components
│   │   └── services/            # API client
│   ├── package.json
│   └── tailwind.config.js
├── neo4j/
│   ├── constraints.cypher       # Database constraints
│   └── indexes.cypher           # Database indexes
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Neo4j 5.x (local installation or Neo4j Aura)
- Anthropic API key (optional, for LLM features)

## Setup

### 1. Neo4j Database

#### Option A: Local Installation

1. [Download and install Neo4j](https://neo4j.com/download/)
2. Start Neo4j and set a password
3. Note the connection URI (default: `bolt://localhost:7687`)

#### Option B: Neo4j Aura (Cloud)

1. Create a free account at [Neo4j Aura](https://neo4j.com/cloud/aura/)
2. Create a new database instance
3. Note the connection URI, username, and password

#### Initialize Schema

Connect to your Neo4j instance and run the schema files:

```cypher
// Run constraints first
:source neo4j/constraints.cypher

// Then run indexes
:source neo4j/indexes.cypher
```

Or via cypher-shell:

```bash
cat neo4j/constraints.cypher | cypher-shell -u neo4j -p <password>
cat neo4j/indexes.cypher | cypher-shell -u neo4j -p <password>
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Neo4j credentials and other settings
```

#### Environment Variables

Edit `backend/.env`:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
ANTHROPIC_API_KEY=sk-ant-your-api-key-here  # Optional
SEC_EDGAR_USER_AGENT=YourCompany admin@yourcompany.com
```

#### Run Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. API documentation at `http://localhost:8000/docs`.

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## API Endpoints

### Health
- `GET /health` - Basic health check
- `GET /health/db` - Database connectivity check

### Companies
- `GET /api/companies` - List companies (paginated)
- `GET /api/companies/search?q=<query>` - Search companies
- `GET /api/companies/{id}` - Get company details
- `GET /api/companies/{id}/ownership-chain` - Get ownership chain
- `GET /api/companies/{id}/subsidiaries` - Get subsidiaries
- `POST /api/companies` - Create company
- `PATCH /api/companies/{id}` - Update company
- `DELETE /api/companies/{id}` - Delete company

### Persons
- `GET /api/persons` - List persons (paginated)
- `GET /api/persons/search?q=<query>` - Search persons
- `GET /api/persons/pep` - List Politically Exposed Persons
- `GET /api/persons/sanctioned` - List sanctioned persons
- `GET /api/persons/{id}` - Get person details
- `GET /api/persons/{id}/companies` - Get associated companies
- `POST /api/persons` - Create person
- `PATCH /api/persons/{id}` - Update person
- `DELETE /api/persons/{id}` - Delete person

### Filings
- `GET /api/filings` - List SEC filings
- `GET /api/filings/form-types` - Get form type counts
- `GET /api/filings/{id}` - Get filing details
- `GET /api/filings/{id}/entities` - Get entities in filing

### Graph Exploration
- `GET /api/graph/entity/{id}` - Get entity neighborhood
- `GET /api/graph/ownership/{id}` - Get ownership structure
- `GET /api/graph/path?source_id=<id>&target_id=<id>` - Find path between entities
- `GET /api/graph/address-clusters` - Find address clusters
- `GET /api/graph/secrecy-jurisdictions` - Find entities in secrecy jurisdictions
- `GET /api/graph/risk-indicators/{id}` - Analyze entity risk indicators

## Neo4j Schema

### Node Types

| Node | Key Properties |
|------|----------------|
| Company | id, name, cik, lei, jurisdiction, status |
| Person | id, name, is_pep, is_sanctioned |
| Address | id, full_address, entity_count |
| Filing | id, accession_number, form_type, filing_date |
| Jurisdiction | code, name, secrecy_score, is_secrecy_jurisdiction |

### Relationship Types

| Relationship | Description |
|--------------|-------------|
| OWNS | Ownership (percentage, is_beneficial) |
| OFFICER_OF | Officer position (title) |
| DIRECTOR_OF | Director position |
| REGISTERED_AT | Entity registration address |
| INCORPORATED_IN | Jurisdiction of incorporation |
| FILED | Company filed SEC document |
| MENTIONED_IN | Entity mentioned in filing |
| RELATED_TO | Generic relationship |
| SAME_AS | Entity resolution match |

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Formatting

```bash
cd backend
black .
ruff check .
```

### Type Checking

```bash
cd backend
mypy app
```

## Next Steps

This is a skeleton project. To build a full beneficial ownership intelligence platform:

1. **Data Ingestion**: Implement SEC EDGAR parsers in `backend/ingestion/sec_edgar/`
2. **Entity Resolution**: Add logic to match and merge duplicate entities
3. **Graph Visualization**: Integrate D3.js or Cytoscape.js in the frontend
4. **Risk Scoring**: Implement weighted risk scoring algorithms
5. **Additional Data Sources**: Add parsers for other data sources (OpenCorporates, GLEIF, etc.)
