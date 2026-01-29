# Data Analyst Agent

This project contains a "Data Analyst Agent," an AI agent built using the Google Agent Development Kit (ADK). The agent acts as a powerful text-to-SQL engine, translating natural language questions into BigQuery SQL queries to retrieve data and insights.

It is designed to connect to a BigQuery database via an MCP (Model Context Protocol) server. MCP is a protocol that allows the agent to discover and interact with external tools and APIs, like BigQuery, in a standardized way. This enables users like business partners or clients to get answers to complex business questions without needing to write SQL themselves.

## Overview

The core of this project is an `LlmAgent` that is instructed to act as a data analyst. It is provided with the schema of the target BigQuery tables and examples of how to construct SQL queries to answer user questions.

For example, a user can ask:

> "How many Data Engineer roles are open in Atlanta?"

The agent will understand this request, translate it into the appropriate SQL query, execute it against BigQuery, and return a human-readable answer.

This drastically reduces the time to deliver analytics and empowers non-technical users to interact with their data directly.

## Key Features

*   **Natural Language to SQL:** Converts user questions into executable BigQuery SQL queries.
*   **BigQuery Integration:** Uses the ADK's `ApiRegistry` and an MCP (Model Context Protocol) server to securely connect and query BigQuery.
*   **Customizable Persona:** The agent's behavior, persona, and knowledge are defined via a detailed instruction prompt.
*   **Error & Response Handling:** Includes custom callbacks to handle query errors (like timeouts) and empty result sets, providing a better user experience.
*   **Deployable:** The agent can be deployed on various platforms like Google Cloud Run, App Engine, etc.

## How It Works

The main logic is in `agent.py`:

1.  **Initialization:** The script initializes an `ApiRegistry` with a Google Cloud Project ID.
2.  **Tool Acquisition:** It retrieves a `toolset` for a specific BigQuery MCP server. This toolset contains functions like `execute_sql` that the agent can call.
3.  **Agent Definition:** An `LlmAgent` is created with:
    *   A detailed `instruction` prompt that tells the agent its role, the database schema it can query, and rules for constructing SQL.
    *   Example user queries and the corresponding tool calls (SQL queries) to guide its behavior.
    *   The `tools` acquired from the `ApiRegistry`.
    *   Custom callback functions (`on_tool_error_callback`, `after_tool_callback`) to manage the tool execution lifecycle.

## Getting Started

### Prerequisites

1.  **Google Cloud Project:** A Google Cloud project with the BigQuery API enabled.
2.  **BigQuery Tables:** The necessary tables must exist in BigQuery. The example uses `job_posting_test_data` and `candidate_test_data`.
3.  **Python Environment:** A Python 3.10+ environment.
4.  **Dependencies:** Install the required libraries.
    ```bash
    pip install google-adk
    ```
5.  **Authentication:** Ensure your environment is authenticated with Google Cloud.
    ```bash
    gcloud auth application-default login
    ```

### Configuration

1.  **Environment Variables:** Create a `.env` file in the project root and add your project ID:
    ```
    GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_REGION="your-desired-region"
    GOOGLE_API_KEY="api-key"
    ```
2.  **Agent Instructions (`agent.py`):** This is the most critical part to customize. Open `my_agent/agent.py` and modify the `instruction` string within the `LlmAgent` definition:
    *   Update the table names to match your BigQuery dataset and tables.
    *   Update the table schemas (column names and descriptions).
    *   Refine the instructions and examples to match your specific data and use case.

## Best Practices for Optimal Performance

The quality of the agent's responses is highly dependent on the underlying data and the instructions provided.

*   **Data Quality:** Ensure your source data is clean. This includes handling nulls, removing duplicates, and standardizing formats (e.g., ensuring all currency fields are in a single currency and all dates use a common timezone).
*   **Schema and Metadata:** Use clear, descriptive names for your BigQuery tables and columns. Populate the `description` field for each table and column in BigQuery, as the agent uses this metadata to better understand the data.
*   **Entity-Relationships:** If your data spans multiple tables, explicitly define the relationships and join keys in the agent's `instruction` prompt. This is crucial for the agent to formulate correct `JOIN` conditions.

## Cost Management and Fine-Tuning

BigQuery costs can increase with the volume of data scanned. The agent can be configured to help manage costs.

*   **Query Cost Evaluation:** You can instruct the agent to first evaluate the cost of a query. If it's too high, the agent can ask the user to provide more filters to narrow down the scope of their request (e.g., "Please specify a date range or region").
*   **Response Tuning:** In the `LlmAgent` configuration, you can use `generate_content_config` to control the model's output:
    *   `temperature`: A lower value (e.g., `0.2`) makes the output more deterministic and less creative.
    *   `max_output_tokens`: Restricts the length of the generated response to control costs and verbosity.

### Example `generate_content_config`

```python
# In agent.py, inside the LlmAgent constructor

# from google.adk.runtime.config import types

generate_content_config=types.GenerateContentConfig(
    temperature=0.2, # More deterministic output
    max_output_tokens=250,
)
```
