import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from databricks.vector_search.client import VectorSearchClient
from mcp.server.fastmcp import FastMCP
import psycopg2

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")


DATABRICKS_HOST = os.environ["DATABRICKS_HOST"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
ENDPOINT_NAME = "career_copilot_endpoint"
INDEX_NAME = "career_copilot.processed.doc_embeddings_index"

LAKEBASE_HOST = os.environ["LAKEBASE_HOST"]
LAKEBASE_PORT = os.environ["LAKEBASE_PORT"]
LAKEBASE_DB = os.environ["LAKEBASE_DB"]
LAKEBASE_USER = os.environ["LAKEBASE_USER"]
LAKEBASE_PASSWORD = os.environ["LAKEBASE_PASSWORD"]

def get_lakebase_connection():
    return psycopg2.connect(
        host=LAKEBASE_HOST,
        port=LAKEBASE_PORT,
        dbname=LAKEBASE_DB,
        user=LAKEBASE_USER,
        password=LAKEBASE_PASSWORD,
        sslmode="require",
    )


# Loaded once when the server starts, reused for every query
model = SentenceTransformer("all-MiniLM-L6-v2")


vsc = VectorSearchClient(
    workspace_url=DATABRICKS_HOST,
    personal_access_token=DATABRICKS_TOKEN,
    disable_notice=True,
)
index = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)


mcp = FastMCP("career-copilot")

@mcp.tool()
def search_career_evidenct(query: str, top_k: int = 5) -> str:
    """Search Shreya's career corpus (resume, project READMEs, case studies,
    design-decision docs) for chunks relevant to the given query. Returns 
    matching chunks with their source file, project name, and doc type."""
    query_vector = model.encode([query])[0].tolist()
    results = index.similarity_search(
        query_vector=query_vector,
        columns=["chunk_id", "source_file", "project_name", "doc_type", "chunk_text"],
        num_results=top_k,
    )
    rows = results.get("result", {}).get("data_array", [])
    if not rows:
        return "No relevant results found."

    formatted = []
    for row in rows:
        chunk_id, source_file, project_name, doc_type, chunk_text, score = row
        formatted.append(
            f"[{project_name} / {doc_type} / {source_file}] (score: {score:.3f})\n{chunk_text}"
        )
    return "\n\n---\n\n".join(formatted)



@mcp.tool()
def log_job_application(company: str, role: str, jd_url: str = "", status: str = "applied", notes: str = "") -> str:
    """Log a new job application to Shreya's tracker. Use this when she says
    she's applying to a role or wants to record an application."""
    conn = get_lakebase_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO job_applications (company, role, jd_url, status, notes)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (company, role, jd_url, status, notes),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return f"Logged application #{new_id}: {role} at {company} (status: {status})"



@mcp.tool()
def update_application_status(company: str, role: str, new_status: str) -> str:
    """Update the status of an existing job application, e.g. moving it from
    'applied' to 'interviewing', 'offer', or 'rejected'."""
    conn = get_lakebase_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE job_applications SET status = %s
           WHERE company = %s AND role = %s
           RETURNING id""",
        (new_status, company, role),
    )
    updated = cur.fetchall()
    conn.commit()
    conn.close()
    if not updated:
        return f"No application found for {role} at {company}."
    return f"Updated {len(updated)} application(s) for {role} at {company} to status '{new_status}'."



@mcp.tool()
def get_case_study(project_name: str) -> str:
    """Fetch the complete case study for a project (e.g. 'week1', 'week2', 'week3'),
    reconstructed in full from its indexed chunks. Use this when Shreya wants the
    whole case study, not just a relevant snippet."""
    query_vector = model.encode([project_name])[0].tolist()
    results = index.similarity_search(
        query_vector=query_vector,
        columns=["project_name", "doc_type", "chunk_index", "chunk_text"],
        filters={"project_name": project_name, "doc_type": "case_study"},
        num_results=50,
    )
    rows = results.get("result", {}).get("data_array", [])
    if not rows:
        return f"No case study found for project '{project_name}'."
    rows.sort(key=lambda r: r[2])  # order by chunk_index
    return "\n\n".join(r[3] for r in rows)



@mcp.tool()
def get_skills_gap(jd_text: str) -> str:
    """Compare a pasted job description against Shreya's career corpus and report
    which mentioned skills she has documented evidence for, and in which project."""
    SKILLS = [
        "Python", "SQL", "dbt", "Airflow", "Kafka", "Spark", "Databricks",
        "Terraform", "AWS", "Docker", "PostgreSQL", "Vector Search", "MCP",
        "PySpark", "Snowflake", "BigQuery", "Redshift", "CI/CD",
    ]
    jd_lower = jd_text.lower()
    relevant = [s for s in SKILLS if s.lower() in jd_lower]
    if not relevant:
        return "No recognized skill keywords found in that job description."

    query_vector = model.encode([" "])[0].tolist()
    results = index.similarity_search(
        query_vector=query_vector,
        columns=["project_name", "chunk_text"],
        num_results=100,
    )
    rows = results.get("result", {}).get("data_array", [])

    lines = ["skill | has_evidence | source_project(s)"]
    for skill in relevant:
        matches = sorted({r[0] for r in rows if skill.lower() in r[1].lower()})
        lines.append(f"{skill} | {'yes' if matches else 'no'} | {', '.join(matches) or '-'}")
    return "\n".join(lines)



if __name__ == "__main__":
    mcp.run()