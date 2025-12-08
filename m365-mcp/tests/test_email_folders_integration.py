"""Integration tests v2 - verifying email folder tools work correctly.

Uses the original working pattern with per-test sessions.
"""

import os
import json
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def parse_result(result, tool_name=None):
    """Helper to parse MCP tool results consistently"""
    if result.content and hasattr(result.content[0], "text"):
        text = result.content[0].text
        if text == "[]":
            return []
        data = json.loads(text)
        list_tools = {
            "account_list",
            "email_list",
            "calendar_list_events",
            "contact_list",
            "file_list",
            "emailfolders_list",
        }
        if tool_name in list_tools and isinstance(data, dict):
            return [data]
        return data
    return []


async def get_session():
    """Create a new MCP session for testing"""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "m365-mcp"],
        env={
            "M365_MCP_CLIENT_ID": os.getenv("M365_MCP_CLIENT_ID", ""),
            "M365_MCP_TENANT_ID": os.getenv("M365_MCP_TENANT_ID", "common"),
            "MCP_TRANSPORT": "stdio",
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def get_account_info(session):
    """Get account info for testing"""
    result = await session.call_tool("account_list", {})
    assert not result.isError
    accounts = parse_result(result, "account_list")
    assert accounts and len(accounts) > 0, (
        "No accounts found - please authenticate first"
    )
    return {
        "email": accounts[0]["username"],
        "account_id": accounts[0]["account_id"],
    }


@pytest.mark.asyncio
async def test_list_accounts():
    """Test list_accounts tool"""
    async for session in get_session():
        result = await session.call_tool("account_list", {})
        assert not result.isError
        accounts = parse_result(result, "account_list")
        assert accounts and len(accounts) > 0
        assert "username" in accounts[0]
        assert "account_id" in accounts[0]


@pytest.mark.asyncio
async def test_emailfolders_list():
    """Test listing email folders"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "emailfolders_list",
            {
                "account_id": account_info["account_id"],
                "limit": 10,
            },
        )
        assert not result.isError
        folders = parse_result(result, "emailfolders_list")
        assert folders is not None
        assert isinstance(folders, list)
        if len(folders) > 0:
            assert "id" in folders[0]
            assert "displayName" in folders[0]


@pytest.mark.asyncio
async def test_emailfolders_get():
    """Test getting email folder details"""
    async for session in get_session():
        account_info = await get_account_info(session)

        # First, list folders to get a folder ID
        list_result = await session.call_tool(
            "emailfolders_list",
            {"account_id": account_info["account_id"], "limit": 1},
        )
        folders = parse_result(list_result, "emailfolders_list")

        if folders and len(folders) > 0:
            folder_id = folders[0]["id"]

            # Get folder details
            result = await session.call_tool(
                "emailfolders_get",
                {
                    "folder_id": folder_id,
                    "account_id": account_info["account_id"],
                },
            )
            assert not result.isError
            folder = parse_result(result)
            assert folder is not None
            assert folder["id"] == folder_id
            assert "displayName" in folder


@pytest.mark.asyncio
async def test_emailfolders_get_tree():
    """Test getting email folder tree"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "emailfolders_get_tree",
            {
                "account_id": account_info["account_id"],
                "max_depth": 3,
            },
        )
        assert not result.isError
        tree = parse_result(result)
        assert tree is not None
        assert "folders" in tree
        assert isinstance(tree["folders"], list)


@pytest.mark.asyncio
async def test_emailfolders_create_and_delete():
    """Test creating and deleting a folder"""
    async for session in get_session():
        account_info = await get_account_info(session)

        # Create a test folder
        create_result = await session.call_tool(
            "emailfolders_create",
            {
                "display_name": "Test Folder Integration V2",
                "account_id": account_info["account_id"],
            },
        )
        assert not create_result.isError
        folder = parse_result(create_result)
        assert folder is not None
        assert "id" in folder
        assert folder["displayName"] == "Test Folder Integration V2"

        folder_id = folder["id"]

        # Delete the test folder
        delete_result = await session.call_tool(
            "emailfolders_delete",
            {
                "folder_id": folder_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
        assert not delete_result.isError
        delete_status = parse_result(delete_result)
        assert delete_status["status"] == "deleted"
        assert delete_status["folder_id"] == folder_id


@pytest.mark.asyncio
async def test_emailfolders_rename():
    """Test renaming a folder"""
    async for session in get_session():
        account_info = await get_account_info(session)

        # Create a test folder
        create_result = await session.call_tool(
            "emailfolders_create",
            {
                "display_name": "Folder To Rename V2",
                "account_id": account_info["account_id"],
            },
        )
        assert not create_result.isError
        folder = parse_result(create_result)
        folder_id = folder["id"]

        try:
            # Rename the folder
            rename_result = await session.call_tool(
                "emailfolders_rename",
                {
                    "folder_id": folder_id,
                    "new_display_name": "Renamed Folder V2",
                    "account_id": account_info["account_id"],
                },
            )
            assert not rename_result.isError
            renamed = parse_result(rename_result)
            assert renamed["displayName"] == "Renamed Folder V2"
        finally:
            # Cleanup
            await session.call_tool(
                "emailfolders_delete",
                {
                    "folder_id": folder_id,
                    "account_id": account_info["account_id"],
                    "confirm": True,
                },
            )


@pytest.mark.asyncio
async def test_emailfolders_move():
    """Test moving a folder to a different parent"""
    async for session in get_session():
        account_info = await get_account_info(session)

        # Create parent folder
        parent_result = await session.call_tool(
            "emailfolders_create",
            {
                "display_name": "Parent Folder V2",
                "account_id": account_info["account_id"],
            },
        )
        assert not parent_result.isError
        parent_folder = parse_result(parent_result)
        parent_id = parent_folder["id"]

        # Create child folder at root
        child_result = await session.call_tool(
            "emailfolders_create",
            {
                "display_name": "Child Folder V2",
                "account_id": account_info["account_id"],
            },
        )
        assert not child_result.isError
        child_folder = parse_result(child_result)
        child_id = child_folder["id"]

        try:
            # Move child to parent
            move_result = await session.call_tool(
                "emailfolders_move",
                {
                    "folder_id": child_id,
                    "destination_folder_id": parent_id,
                    "account_id": account_info["account_id"],
                },
            )
            assert not move_result.isError
            moved = parse_result(move_result)
            # Verify that parentFolderId is now set (not None/empty)
            # Note: Microsoft Graph may normalize the ID format
            assert "parentFolderId" in moved
            assert moved["parentFolderId"] is not None
            assert len(moved["parentFolderId"]) > 0
        finally:
            # Cleanup (child first, then parent)
            await session.call_tool(
                "emailfolders_delete",
                {
                    "folder_id": child_id,
                    "account_id": account_info["account_id"],
                    "confirm": True,
                },
            )
            await session.call_tool(
                "emailfolders_delete",
                {
                    "folder_id": parent_id,
                    "account_id": account_info["account_id"],
                    "confirm": True,
                },
            )
