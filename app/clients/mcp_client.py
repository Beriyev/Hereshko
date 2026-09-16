from typing import Any

from groq.types.chat import ChatCompletionToolParam
from mcp import Client
from mcp.types import CallToolResult, TextContent, Tool


def _tool_spec(tool: Tool) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def result_text(result: CallToolResult) -> str:
    text_parts = []
    for block in result.content:
        if isinstance(block, TextContent):
            text_parts.append(block.text)
    if text_parts:
        return "\n".join(text_parts)
    if result.structured_content is not None:
        return str(result.structured_content)
    return ""


async def get_tool_specs(client: Client) -> list[ChatCompletionToolParam]:
    tools = await client.list_tools()
    tool_specs_list = []

    for tool in tools.tools:
        tool_specs_list.append(_tool_spec(tool=tool))

    return tool_specs_list


async def call_tool(client: Client, name: str, arguments: dict[str, Any]) -> CallToolResult:
    result = await client.call_tool(name=name, arguments=arguments)
    return result
