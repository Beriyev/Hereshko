from typing import Any

from mcp import Client
from mcp.types import CallToolResult, TextContent, Tool


def _tool_spec(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def _result_text(result: CallToolResult) -> str:
    text_parts = []
    for block in result.content:
        if isinstance(block, TextContent):
            text_parts.append(block.text)
    if text_parts:
        return "\n".join(text_parts)
    if result.structured_content is not None:
        return str(result.structured_content)
    return ""


async def get_tool_specs(client: Client) -> list[dict[str, Any]]:
    tools = await client.list_tools()
    tool_specs_list = []

    for tool in tools.tools:
        tool_specs_list.append(_tool_spec(tool=tool))

    return tool_specs_list


async def call_tool(client: Client, name: str, arguments: dict[str, Any]) -> str:
    result = await client.call_tool(name=name, arguments=arguments)
    if result.is_error:
        return f"Tool error ({name}): {_result_text(result)}"
    return _result_text(result=result)
