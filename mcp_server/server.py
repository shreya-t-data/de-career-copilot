import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from databricks.vector_search.client import VectorSearchClient
from mcp.server.fastmcp import FastMCP

from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")


DATABRICKS_HOST = os.environ["DATABRICKS_HOST"]
DATABRICKS_TOKEN = os.environ["DATABRICKS_TOKEN"]
ENDPOINT_NAME = "career_copilot_endpoint"
INDEX_NAME = "career_copilot.processed.doc_embeddings_index"


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

if __name__ == "__main__":
    mcp.run()