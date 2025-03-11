from langgraph_sdk import get_client

url_for_cli_deployment = "http://localhost:8123"
client = get_client(url=url_for_cli_deployment)

client.http()