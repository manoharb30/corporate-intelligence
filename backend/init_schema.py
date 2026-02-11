"""Initialize Neo4j schema (constraints and indexes)."""

import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def run_cypher_file(driver, filepath: Path) -> None:
    """Run all Cypher statements from a file."""
    content = filepath.read_text()

    # Split by semicolon and filter out comments/empty lines
    statements = []
    for stmt in content.split(";"):
        # Remove comments and whitespace
        lines = []
        for line in stmt.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("//"):
                lines.append(line)
        if lines:
            statements.append(" ".join(lines))

    with driver.session() as session:
        for stmt in statements:
            if stmt.strip():
                try:
                    session.run(stmt)
                    print(f"✓ {stmt[:60]}...")
                except Exception as e:
                    print(f"✗ {stmt[:60]}... - {e}")


def main():
    print(f"Connecting to Neo4j at {NEO4J_URI}...")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Verify connectivity
    driver.verify_connectivity()
    print("✓ Connected to Neo4j\n")

    neo4j_dir = Path(__file__).parent.parent / "neo4j"

    # Run constraints
    print("=== Creating Constraints ===")
    run_cypher_file(driver, neo4j_dir / "constraints.cypher")

    print("\n=== Creating Indexes ===")
    run_cypher_file(driver, neo4j_dir / "indexes.cypher")

    driver.close()
    print("\n✓ Schema initialization complete!")


if __name__ == "__main__":
    main()
