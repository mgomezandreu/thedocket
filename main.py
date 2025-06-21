# main.py
import os
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool, VertexAiSearchTool
from google.adk.runners import InMemoryRunner
# New import for listing data stores
from google.cloud import discoveryengine_v1alpha as discoveryengine

# --- Architecture Overview ---
# This version simplifies the workflow by always searching all available data stores.
# It removes the need for an agent to select which stores to search.
#
# 1.  SearchCoordinatorAgent: Uses a single tool to list all available data stores
#     and immediately performs a search in each one, aggregating the results.
# 2.  AnalysisAgent: Reasons over the comprehensive, multi-source data.
# 3.  SummarizerAgent: Formats the final report.

# --- Agent 1: Search Coordinator ---

def list_and_search_all_stores(project_id: str, query: str, location: str = "global") -> str:
    """
    Lists all data stores in the project, then performs a search in each one
    and aggregates the results.
    """
    all_results = []
    print(f"--- Starting search across all data stores in project {project_id} ---")

    # Step 1: List all available data stores
    try:
        client = discoveryengine.DataStoreServiceClient()
        parent = f"projects/{project_id}/locations/{location}/collections/default_collection"
        response = client.list_data_stores(parent=parent)
        datastore_ids = [s.name.split('/')[-1] for s in response]
        print(f"--- Found {len(datastore_ids)} data stores to search. ---")
    except Exception as e:
        return f"Error: Could not list data stores. {e}"

    # Step 2: Iterate and search each data store
    for store_id in datastore_ids:
        print(f"--- Searching in data store: {store_id} ---")
        try:
            # In a real async application, you would await this call.
            search_tool = VertexAiSearchTool(data_store_id=store_id)
            # This is a simulation of the result for demonstration.
            result_snippet = f"Retrieved document from {store_id} related to '{query}'."
            all_results.append(result_snippet)
        except Exception as e:
            all_results.append(f"Error searching in {store_id}: {e}")
            
    return "\n\n".join(all_results)

# Create a single tool for the combined list-and-search function
search_all_tool = FunctionTool(list_and_search_all_stores)

# This is now the first agent in the sequence.
search_coordinator_agent = LlmAgent(
    name="SearchCoordinatorAgent",
    description="Coordinates a comprehensive search across all available data stores.",
    tools=[search_all_tool],
    instruction="""You must call the `list_and_search_all_stores` tool to get all relevant information.
    Use the user's original query as the input for the search."""
)


# --- Agent 2: Analysis Agent ---
analysis_agent = LlmAgent(
    name="AnalysisAgent",
    description="Analyzes a collection of texts from all sources to find connections.",
    instruction="""You will be given a collection of text snippets from all internal databases. Your tasks are:
    1. Identify the key entities (e.g., lawyers, clients, regulations).
    2. Determine the relationships between these entities based on all available text.
    3. Analyze these relationships to infer the potential impact of events on the lawyer's clients.
    4. Output a structured analysis of these findings."""
)


# --- Agent 3: Summarizer Agent ---
summarizer_agent = LlmAgent(
    name="SummarizerAgent",
    description="Formats a structured analysis into a final report.",
    instruction="""You will be given a structured analysis. Format it into a clear, well-organized final summary."""
)

# --- Orchestrator: Sequential Agent ---
# The workflow is now simpler: Coordinate Search -> Analyze -> Summarize.
root_agent = SequentialAgent(
    name="RootAgent",
    sub_agents=[search_coordinator_agent, analysis_agent, summarizer_agent]
)

# --- Run the Application ---
if __name__ == "__main__":
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("Please set the GOOGLE_CLOUD_PROJECT environment variable.")
    else:
        runner = InMemoryRunner(agent=root_agent, app_name="legal-research-agent")
        
        initial_message = "Tell me about finance lawyer John Smith and his relation to the Capital Markets Reform Act."
        
        print(f"Starting agent workflow for initial query: '{initial_message}'")
        print("-" * 30)
        
        # We need to provide the project_id and the query to the search tool.
        events = runner.run(
            user_id="legal_analyst_05", 
            session_id="session_search_all_001", 
            new_message=initial_message,
            run_config={"tool_input": {"list_and_search_all_stores": {"project_id": project, "query": initial_message}}}
        )

        print("-" * 30)
        print("--- Agent Workflow Complete ---")
        for event in events:
            if event.is_final_response():
                print("\nFinal Analysis Report:")
                print(event.parts[0].text)