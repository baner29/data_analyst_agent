import os
import google.adk as adk
from google.api_core import exceptions as api_exceptions
from google.adk.agents import LlmAgent
from google.adk.tools.api_registry import ApiRegistry
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from typing import Any, Dict, Optional, Union, Awaitable

# Get project ID from environment variables, which are loaded from .env
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
MCP_SERVER_NAME = f"projects/{PROJECT_ID}/locations/global/mcpServers/google-bigquery.googleapis.com-mcp"

# Initialize the ApiRegistry with the project ID
api_registry = ApiRegistry(PROJECT_ID)

# Get the toolset for the BigQuery MCP server
registry_tools = api_registry.get_toolset(mcp_server_name=MCP_SERVER_NAME)

def _get_root_exception(e: Exception) -> Exception:
    """Recursively unwraps an exception to find the root cause."""
    if e.__cause__ is None:
        return e
    return _get_root_exception(e.__cause__)


async def handle_bigquery_tool_error(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    error: Exception,
) -> Optional[Dict[str, Any]]:
    """Custom error handler for BigQuery tool calls."""
    logger = tool_context._invocation_context.logger
    logger.error(f"Error executing tool '{tool.name}' with args {args}: {error}")

    # Unwrap the exception to find the root cause.
    root_exception = _get_root_exception(error)
    if isinstance(root_exception, api_exceptions.BadRequest):
        return {
            "error_message": "I was unable to run the query as it seems to be invalid. Please try rephrasing your request."
        }

    # Check if the error is a timeout and provide a specific message
    if "Timed out" in str(error):
        error_message = (
            "The database query took too long to execute and timed out. "
            "This can happen with complex questions on large datasets. "
            "Please try asking a more specific question."
        )
    else:
        error_message = (
            "I encountered an error while trying to query the database. "
            "Please try rephrasing your request."
        )

    # Return a user-friendly error message. The agent will then present this to the user.
    return {"error_message": error_message}

async def after_bigquery_tool_call(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Union[Dict[str, Any], list[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Custom handler for BigQuery tool calls to handle errors and empty results."""
    if isinstance(tool_response, dict):
        # Handle errors returned by the BigQuery tool.
        if tool_response.get("status") == "ERROR":
            logger = tool_context._invocation_context.logger
            error_details = tool_response.get("error_details", "Unknown error")
            logger.error(f"BigQuery tool returned an error: {error_details}")
            return {
                "error_message": "I encountered an error while trying to query the database. Please try rephrasing your request."
            }

        # Handle empty results for SELECT queries.
        if "rows" in tool_response and not tool_response["rows"]:
            return {
                "message": "I couldn't find any information matching your criteria in the database. Please try a different search or broaden your criteria."
            }

    # Handle empty results when the response is a list.
    if isinstance(tool_response, list) and not tool_response:
        return {
            "message": "I couldn't find any information matching your criteria in the database. Please try a different search or broaden your criteria."
        }
    return None # Let the original response pass through if not empty

root_agent = LlmAgent(
  name='data_analyst_agent',
  model='gemini-2.5-flash',
  description=(
      'An agent that can answer questions about job openings and candidates from a database.'
  ),
  instruction=(
    'You are a data analyst. Your goal is to help users find information about'
    ' job openings and candidates from a BigQuery database.\n'
    'All questions should be answered by constructing and running SQL queries against the tables'
    f' `{PROJECT_ID}.test_chat_bot.job_posting_test_data` and `{PROJECT_ID}.test_chat_bot.candidate_test_data`.\n\n'
    'The table schemas are as follows:\n\n'
    f'Table: `{PROJECT_ID}.test_chat_bot.job_posting_test_data`\n'
    '- job_id (STRING): Unique identifier for the job posting.\n'
    '- job_title (STRING): The title of the job posting.\n'
    '- city (STRING): The city and/or state of the job.\n'
    '- country (STRING): The country where the job is located.\n'
    '- salary_min (FLOAT): The minimum salary for the role.\n'
    '- salary_max (FLOAT): The maximum salary for the role.\n'
    '- post_date (DATE): The date the job was posted.\n'
    f'\nTable: `{PROJECT_ID}.test_chat_bot.candidate_test_data`\n'
    '- candidate_id (STRING): Unique identifier for the candidate.\n'
    '- job_id (STRING): The job ID the candidate applied for. This can be used to join with the job_posting_test_data table.\n'
    '- first_name (STRING): The first name of the candidate.\n'
    '- last_name (STRING): The last name of the candidate.\n'
    '- email (STRING): The email address of the candidate.\n'
    '- linkedin_profile (STRING): The LinkedIn URL of the candidate.\n'
    '- resume_link (STRING): The URL of the candidate\'s resume.\n'
    '- application_date (DATE): The date the candidate applied.\n'
    '- application_status (DATE): The status of the candidate application (Applied, Rejected, etc.).\n'
    '- referral_source (STRING): The source from where the candidate applied (e.g., LinkedIn, Indeed).\n'
    '- skills (STRING): A comma-separated list of the candidate\'s skills.\n\n'
    'ensure that whenever applying filters in the BigQuery queries always do lower(column_name) like lower(\'user provided filter criteria\') instead of simple equal to (=) filter unless the user specifically requests to apply exact string or value match\n'
    'When a user asks about a country, you must use the `country` column in your SQL query. '
    'When a user asks about a city or state, use the `city` column.\n'
    'To get insights about candidates for a job, you must join the two tables on `job_id`.\n'
    'If a query returns no results, inform the user that no matching information was found.'
    'If an error occurs during the query, inform the user about the error and suggest rephrasing the question.\n\n'
    'Here are some examples of how to respond to user queries:\n\n'
    'User: How many Data Engineer roles are open in Atlanta?\n'
    'Model: Thought: I need to count the rows in the jobs table where the title is \'Data Engineer\' and the country is \'Atlanta\'.\n'
    'Tool Call: google-bigquery.googleapis.com-mcp:execute_sql(query="SELECT count(*) as job_count FROM '
    f'`{PROJECT_ID}.test_chat_bot.job_posting_test_data` WHERE job_title = \'Data Engineer\' AND city = \'Atlanta\'")\n\n'
    'User: What is the average salary for senior roles?\n'
    'Model: Thought: I will filter for roles containing \'Senior\' and calculate the average of the salary column.\n'
    'Tool Call: google-bigquery.googleapis.com-mcp:execute_sql(query="SELECT AVG(salary_max) as avg_salary FROM '
    f'`{PROJECT_ID}.test_chat_bot.job_posting_test_data` WHERE job_title LIKE \'%Senior%\'")\n\n'
    'User: How many candidates applied for Data Scientist roles?\n'
    'Model: Thought: I need to join the job postings and candidate tables on job_id, filter for \'Data Scientist\' roles, and then count the number of candidates.\n'
    f'Tool Call: google-bigquery.googleapis.com-mcp:execute_sql(query="SELECT COUNT(c.candidate_id) FROM `{PROJECT_ID}.test_chat_bot.candidate_test_data` c JOIN `{PROJECT_ID}.test_chat_bot.job_posting_test_data` j ON c.job_id = j.job_id WHERE j.job_title = \'Data Scientist\'")'
  ),
  # Provide the toolset from the ApiRegistry to the agent
  tools=[registry_tools],
  on_tool_error_callback=handle_bigquery_tool_error,
  after_tool_callback=after_bigquery_tool_call,

  #You can adjust how the underlying LLM generates responses using generate_content_config.
#   generate_content_config=types.GenerateContentConfig(
#         temperature=0.2, # More deterministic output
#         max_output_tokens=250,
#         safety_settings=[
#             types.SafetySetting(
#                 category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
#                 threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
#             )
#         ]
#     )
)