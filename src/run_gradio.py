from __future__ import annotations

import json
from typing import Any

import gradio as gr
from gradio import ChatMessage
from gradio.components.chatbot import MetadataDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from agent import agent, tools


def _extract_content(value: Any) -> str:
    """Extract text content from LangChain responses."""

    if isinstance(value, str):
        return value

    if isinstance(value, BaseMessage):
        return str(value.content)

    if isinstance(value, dict):
        # Check for messages list (common agent response)
        if "messages" in value and value["messages"]:
            last_msg = value["messages"][-1]
            if isinstance(last_msg, BaseMessage):
                return str(last_msg.content)
            if isinstance(last_msg, dict) and "content" in last_msg:
                return str(last_msg["content"])

        # Check common output keys
        for key in ("output", "content", "answer"):
            if key in value:
                return _extract_content(value[key])

    if isinstance(value, list) and value:
        last = value[-1]
        if isinstance(last, BaseMessage):
            return str(last.content)

    return str(value)


def _format_history_for_agent(history: list[ChatMessage]) -> list[BaseMessage]:
    formatted: list[BaseMessage] = []
    for msg in history:
        if msg.role not in {"user", "assistant"}:
            continue

        if msg.role == "assistant" and msg.metadata:
            # Skip assistant tool/thought messages when forwarding to the agent
            continue

        content = _extract_content(msg.content)
        if content:
            if msg.role == "user":
                formatted.append(HumanMessage(content=content))
            else:
                formatted.append(AIMessage(content=content))
    return formatted


def _format_tool_metadata(tool_call: dict[str, Any], tool_response: ToolMessage | None) -> tuple[str, MetadataDict]:
    tool_name = tool_call.get("name", "unknown")
    metadata: MetadataDict = {"title": f"🛠️ Used `{tool_name}`", "status": "done"}

    args = tool_call.get("args") or tool_call.get("arguments")
    if args:
        if isinstance(args, str):
            log = args
        else:
            try:
                log = json.dumps(args, ensure_ascii=False)
            except (TypeError, ValueError):
                log = str(args)
        metadata["log"] = log[:50] + ("..." if len(log) > 50 else "")

    content = str(tool_response.content) if tool_response else f"Called `{tool_name}`."

    return content, metadata


def respond(
    message: ChatMessage | str,
    history: list[ChatMessage],
    conversation_state: list[BaseMessage] | None = None,
) -> tuple[list[ChatMessage] | ChatMessage, list[BaseMessage]]:
    """Gradio callback to forward the conversation to the LangChain agent."""

    user_text = _extract_content(message.content) if isinstance(message, ChatMessage) else str(message)

    # Reset stored state when starting a new conversation
    if not history:
        conversation_state = []

    messages: list[BaseMessage] = list(conversation_state or _format_history_for_agent(history))
    messages.append(HumanMessage(content=user_text))
    base_length: int = len(messages)

    try:
        result = agent.invoke({"messages": messages})  # type: ignore[arg-type]

        response_text = _extract_content(result)

        tool_messages: list[ChatMessage] = []

        if isinstance(result, dict) and "messages" in result:
            messages = list(result["messages"])
        else:
            messages.append(AIMessage(content=response_text))

        # Get messages since last user input
        recent_messages = messages[base_length:] if len(messages) >= base_length else []
        # filter(lambda m: isinstance(m, ToolMessage), recent_messages):
        for i, msg in enumerate(recent_messages):
            tool_calls: list[dict[str, Any]] | None = getattr(msg, "tool_calls", None)
            if not tool_calls:
                continue

            for tool_call in tool_calls:
                call_id = tool_call.get("id", f"call_{i}")
                tool_response = next(
                    (
                        m
                        for m in recent_messages[i + 1 :]
                        if isinstance(m, ToolMessage) and getattr(m, "tool_call_id", None) == call_id
                    ),
                    None,
                )
                content, metadata = _format_tool_metadata(tool_call, tool_response)
                tool_messages.append(
                    ChatMessage(
                        role="assistant",
                        content=content,
                        metadata=metadata,
                    )
                )

        final_message = ChatMessage(role="assistant", content=response_text)

        if tool_messages:
            tool_messages.append(final_message)
            return tool_messages, messages

        return final_message, messages
    except Exception as exc:
        error_message = ChatMessage(role="assistant", content=f"⚠️ Agent error: {exc}")
        return error_message, messages


def render_tools() -> None:
    """Generate markdown list of available tools."""
    if not tools:
        gr.Label("No tools available.")
        return

    gr.Markdown("## Available Tools")
    for tool in tools:
        tool_name = tool.name if hasattr(tool, "name") else str(tool)
        tool_desc = tool.description if hasattr(tool, "description") else "No description available"

        with gr.Accordion(tool_name, open=True):
            gr.Markdown(tool_desc)


with gr.Blocks(title="Email Agent") as demo:
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("# Email Agent")
            gr.Markdown("---")
            render_tools()

        with gr.Column(scale=3):
            conversation_state = gr.State(None)
            chat = gr.ChatInterface(
                fn=respond,
                chatbot=gr.Chatbot(type="messages", height="80dvh"),
                type="messages",
                additional_inputs=[conversation_state],
                additional_outputs=[conversation_state],
                fill_height=True,
                multimodal=True,
            )


if __name__ == "__main__":
    demo.launch(
        debug=True,
    )
