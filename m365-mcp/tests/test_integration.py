"""Integration tests v3 - complete test suite with working pattern.

Migrating all 36 tests from test_integration.py using the proven working pattern.
"""

import os
import asyncio
import json
from datetime import datetime, timedelta, timezone
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
        "account_type": accounts[0].get("account_type", "unknown"),
    }


@pytest.mark.asyncio
async def test_list_accounts():
    """Test list_accounts tool"""
    async for session in get_session():
        result = await session.call_tool("account_list", {})
        assert not result.isError
        accounts = parse_result(result, "account_list")
        assert accounts is not None
        assert len(accounts) > 0
        assert "username" in accounts[0]
        assert "account_id" in accounts[0]
        assert "account_type" in accounts[0]
        # account_type should be one of: "personal", "work_school", or "unknown"
        assert accounts[0]["account_type"] in ["personal", "work_school", "unknown"]


@pytest.mark.asyncio
async def test_list_emails():
    """Test list_emails tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "email_list",
            {
                "account_id": account_info["account_id"],
                "limit": 3,
                "include_body": True,
            },
        )
        assert not result.isError
        emails = parse_result(result, "email_list")
        assert emails is not None
        if len(emails) > 0:
            assert "id" in emails[0]
            assert "subject" in emails[0]
            assert "body" in emails[0]


@pytest.mark.asyncio
async def test_list_emails_without_body():
    """Test list_emails without body content"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "email_list",
            {
                "account_id": account_info["account_id"],
                "limit": 3,
                "include_body": False,
            },
        )
        assert not result.isError
        emails = parse_result(result, "email_list")
        assert emails is not None
        if len(emails) > 0:
            assert "id" in emails[0]
            assert "subject" in emails[0]
            # Body should not be present or should be None/empty
            assert "body" not in emails[0] or emails[0].get("body") in [None, ""]


@pytest.mark.asyncio
async def test_get_email():
    """Test get_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        # First list emails to get an email ID
        list_result = await session.call_tool(
            "email_list",
            {"account_id": account_info["account_id"], "limit": 1},
        )
        emails = parse_result(list_result, "email_list")

        if emails and len(emails) > 0:
            email_id = emails[0]["id"]
            result = await session.call_tool(
                "email_get",
                {
                    "email_id": email_id,
                    "account_id": account_info["account_id"],
                },
            )
            assert not result.isError
            email = parse_result(result)
            assert email is not None
            assert email["id"] == email_id


@pytest.mark.asyncio
async def test_create_email_draft():
    """Test create_email_draft tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "email_create_draft",
            {
                "account_id": account_info["account_id"],
                "to": account_info["email"],
                "subject": "Test Draft V3",
                "body": "This is a test draft from integration test v3",
            },
        )
        assert not result.isError
        draft = parse_result(result)
        assert draft is not None
        assert "id" in draft
        assert draft["subject"] == "Test Draft V3"


@pytest.mark.asyncio
async def test_update_email():
    """Test update_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        # First get an email
        list_result = await session.call_tool(
            "email_list",
            {"account_id": account_info["account_id"], "limit": 1},
        )
        emails = parse_result(list_result, "email_list")

        if emails and len(emails) > 0:
            email_id = emails[0]["id"]
            result = await session.call_tool(
                "email_update",
                {
                    "email_id": email_id,
                    "updates": {"isRead": True},
                    "account_id": account_info["account_id"],
                },
            )
            assert not result.isError


@pytest.mark.asyncio
async def test_delete_email():
    """Test delete_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        # Create a draft first
        draft_result = await session.call_tool(
            "email_create_draft",
            {
                "account_id": account_info["account_id"],
                "to": account_info["email"],
                "subject": "MCP Test Delete",
                "body": "This email will be deleted",
            },
        )
        draft_data = parse_result(draft_result)
        if draft_data and "id" in draft_data:
            result = await session.call_tool(
                "email_delete",
                {
                    "email_id": draft_data["id"],
                    "account_id": account_info["account_id"],
                    "confirm": True,
                },
            )
            assert not result.isError
            delete_result = parse_result(result)
            assert delete_result is not None
            assert delete_result["status"] == "deleted"


@pytest.mark.asyncio
async def test_move_email():
    """Test move_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        list_result = await session.call_tool(
            "email_list",
            {"account_id": account_info["account_id"], "folder": "inbox", "limit": 1},
        )
        emails = parse_result(list_result, "email_list")

        if emails and len(emails) > 0:
            email_id = emails[0]["id"]
            result = await session.call_tool(
                "email_move",
                {
                    "email_id": email_id,
                    "account_id": account_info["account_id"],
                    "destination_folder": "archive",
                },
            )
            assert not result.isError

            move_result = parse_result(result, "email_move")
            new_email_id = move_result.get("new_id", email_id)

            # Move back to inbox
            restore_result = await session.call_tool(
                "email_move",
                {
                    "email_id": new_email_id,
                    "account_id": account_info["account_id"],
                    "destination_folder": "inbox",
                },
            )
            assert not restore_result.isError


@pytest.mark.asyncio
async def test_reply_to_email():
    """Test reply_to_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        await asyncio.sleep(2)
        list_result = await session.call_tool(
            "email_list", {"account_id": account_info["account_id"], "limit": 5}
        )
        emails = parse_result(list_result, "email_list")

        test_email = None
        if emails:
            test_email = next(
                (e for e in emails if "MCP Test" in e.get("subject", "")),
                emails[0] if emails else None,
            )

        if test_email:
            result = await session.call_tool(
                "email_reply",
                {
                    "account_id": account_info["account_id"],
                    "email_id": test_email["id"],
                    "body": "This is a test reply",
                    "confirm": True,
                },
            )
            assert not result.isError
            reply_result = parse_result(result)
            assert reply_result is not None
            assert reply_result["status"] == "sent"


@pytest.mark.asyncio
async def test_email_reply_all():
    """Test email_reply_all tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        await asyncio.sleep(2)
        list_result = await session.call_tool(
            "email_list", {"account_id": account_info["account_id"], "limit": 5}
        )
        emails = parse_result(list_result, "email_list")

        test_email = None
        if emails:
            test_email = next(
                (e for e in emails if "MCP Test" in e.get("subject", "")),
                emails[0] if emails else None,
            )

        if test_email:
            result = await session.call_tool(
                "email_reply_all",
                {
                    "account_id": account_info["account_id"],
                    "email_id": test_email["id"],
                    "body": "This is a test reply to all",
                    "confirm": True,
                },
            )
            assert not result.isError
            reply_result = parse_result(result)
            assert reply_result is not None
            assert reply_result["status"] == "sent"


@pytest.mark.asyncio
async def test_list_events():
    """Test list_events tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "calendar_list_events",
            {
                "account_id": account_info["account_id"],
                "days_ahead": 14,
                "include_details": True,
            },
        )
        assert not result.isError
        events = parse_result(result, "calendar_list_events")
        assert events is not None
        if len(events) > 0:
            assert "id" in events[0]
            assert "subject" in events[0]
            assert "start" in events[0]
            assert "end" in events[0]


@pytest.mark.asyncio
async def test_get_event():
    """Test get_event tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        list_result = await session.call_tool(
            "calendar_list_events",
            {"account_id": account_info["account_id"], "days_ahead": 30},
        )
        events = parse_result(list_result, "calendar_list_events")

        if events and len(events) > 0:
            event_id = events[0]["id"]
            result = await session.call_tool(
                "calendar_get_event",
                {"event_id": event_id, "account_id": account_info["account_id"]},
            )
            assert not result.isError
            event_detail = parse_result(result)
            assert event_detail is not None
            assert "id" in event_detail
            assert event_detail["id"] == event_id


@pytest.mark.asyncio
async def test_create_event():
    """Test create_event tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        start_time = datetime.now(timezone.utc) + timedelta(days=7)
        end_time = start_time + timedelta(hours=1)

        result = await session.call_tool(
            "calendar_create_event",
            {
                "account_id": account_info["account_id"],
                "subject": "MCP Integration Test Event V3",
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "location": "Virtual Meeting Room",
                "body": "This is a test event created by integration tests v3",
                "attendees": [account_info["email"]],
            },
        )
        assert not result.isError
        event_data = parse_result(result)
        assert event_data is not None
        assert "id" in event_data

        event_id = event_data["id"]
        delete_result = await session.call_tool(
            "calendar_delete_event",
            {
                "account_id": account_info["account_id"],
                "event_id": event_id,
                "send_cancellation": False,
                "confirm": True,
            },
        )
        assert not delete_result.isError


@pytest.mark.asyncio
async def test_update_event():
    """Test update_event tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        start_time = datetime.now(timezone.utc) + timedelta(days=8)
        end_time = start_time + timedelta(hours=1)

        create_result = await session.call_tool(
            "calendar_create_event",
            {
                "account_id": account_info["account_id"],
                "subject": "MCP Test Event for Update V3",
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
        )
        event_data = parse_result(create_result)
        assert event_data is not None
        event_id = event_data["id"]

        new_start = start_time + timedelta(hours=2)
        new_end = new_start + timedelta(hours=1)

        result = await session.call_tool(
            "calendar_update_event",
            {
                "event_id": event_id,
                "account_id": account_info["account_id"],
                "updates": {
                    "subject": "MCP Test Event V3 (Updated)",
                    "start": new_start.isoformat(),
                    "end": new_end.isoformat(),
                    "location": "Conference Room B",
                },
            },
        )
        assert not result.isError

        delete_result = await session.call_tool(
            "calendar_delete_event",
            {
                "account_id": account_info["account_id"],
                "event_id": event_id,
                "send_cancellation": False,
                "confirm": True,
            },
        )
        assert not delete_result.isError


@pytest.mark.asyncio
async def test_delete_event():
    """Test delete_event tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        start_time = datetime.now(timezone.utc) + timedelta(days=9)
        end_time = start_time + timedelta(hours=1)

        create_result = await session.call_tool(
            "calendar_create_event",
            {
                "account_id": account_info["account_id"],
                "subject": "MCP Test Event for Deletion V3",
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
        )
        event_data = parse_result(create_result)
        assert event_data is not None
        event_id = event_data["id"]

        result = await session.call_tool(
            "calendar_delete_event",
            {
                "account_id": account_info["account_id"],
                "event_id": event_id,
                "send_cancellation": False,
                "confirm": True,
            },
        )
        assert not result.isError
        delete_result = parse_result(result)
        assert delete_result is not None
        assert delete_result["status"] == "deleted"


@pytest.mark.asyncio
async def test_respond_event():
    """Test respond_event tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        list_result = await session.call_tool(
            "calendar_list_events",
            {"account_id": account_info["account_id"], "days_ahead": 30},
        )
        events = parse_result(list_result, "calendar_list_events")

        if events:
            invite_event = next(
                (e for e in events if e.get("attendees") and len(e["attendees"]) > 1),
                None,
            )
            if invite_event:
                result = await session.call_tool(
                    "calendar_respond_event",
                    {
                        "account_id": account_info["account_id"],
                        "event_id": invite_event["id"],
                        "response": "tentativelyAccept",
                        "message": "I might be able to attend",
                    },
                )
                if not result.isError:
                    response_result = parse_result(result)
                    assert response_result is not None
                    assert response_result["status"] == "tentativelyAccept"


@pytest.mark.asyncio
async def test_check_availability():
    """Test check_availability tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        check_start = (
            (datetime.now(timezone.utc) + timedelta(days=1))
            .replace(hour=10, minute=0)
            .isoformat()
        )
        check_end = (
            (datetime.now(timezone.utc) + timedelta(days=1))
            .replace(hour=17, minute=0)
            .isoformat()
        )

        result = await session.call_tool(
            "calendar_check_availability",
            {
                "account_id": account_info["account_id"],
                "start": check_start,
                "end": check_end,
                "attendees": [account_info["email"]],
            },
        )
        assert not result.isError
        availability = parse_result(result)
        assert availability is not None


@pytest.mark.asyncio
async def test_list_contacts():
    """Test list_contacts tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "contact_list", {"account_id": account_info["account_id"], "limit": 10}
        )
        assert not result.isError
        contacts = parse_result(result, "contact_list")
        assert contacts is not None
        if len(contacts) > 0:
            assert "id" in contacts[0]


@pytest.mark.asyncio
async def test_get_contact():
    """Test get_contact tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        list_result = await session.call_tool(
            "contact_list", {"account_id": account_info["account_id"], "limit": 1}
        )
        assert not list_result.isError
        contacts = parse_result(list_result, "contact_list")
        if contacts and len(contacts) > 0:
            contact_id = contacts[0]["id"]
            result = await session.call_tool(
                "contact_get",
                {"contact_id": contact_id, "account_id": account_info["account_id"]},
            )
            assert not result.isError
            contact_detail = parse_result(result)
            assert contact_detail is not None
            assert "id" in contact_detail


@pytest.mark.asyncio
async def test_create_contact():
    """Test create_contact tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "contact_create",
            {
                "account_id": account_info["account_id"],
                "given_name": "MCP",
                "surname": "TestContactV3",
                "email_addresses": ["mcp.test.v3@example.com"],
                "phone_numbers": {"mobile": "+1234567890"},
            },
        )
        assert not result.isError
        new_contact = parse_result(result)
        assert new_contact is not None
        assert "id" in new_contact

        contact_id = new_contact["id"]
        delete_result = await session.call_tool(
            "contact_delete",
            {
                "contact_id": contact_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
        assert not delete_result.isError


@pytest.mark.asyncio
async def test_update_contact():
    """Test update_contact tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        create_result = await session.call_tool(
            "contact_create",
            {
                "account_id": account_info["account_id"],
                "given_name": "MCPUpdateV3",
                "surname": "Test",
            },
        )
        assert not create_result.isError
        new_contact = parse_result(create_result)
        contact_id = new_contact["id"]

        result = await session.call_tool(
            "contact_update",
            {
                "contact_id": contact_id,
                "account_id": account_info["account_id"],
                "updates": {"givenName": "MCPUpdatedV3"},
            },
        )
        assert not result.isError

        delete_result = await session.call_tool(
            "contact_delete",
            {
                "contact_id": contact_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
        assert not delete_result.isError


@pytest.mark.asyncio
async def test_delete_contact():
    """Test delete_contact tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        create_result = await session.call_tool(
            "contact_create",
            {
                "account_id": account_info["account_id"],
                "given_name": "MCPDeleteV3",
                "surname": "Test",
            },
        )
        assert not create_result.isError
        new_contact = parse_result(create_result)
        contact_id = new_contact["id"]

        result = await session.call_tool(
            "contact_delete",
            {
                "contact_id": contact_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
        assert not result.isError
        delete_result = parse_result(result)
        assert delete_result is not None
        assert delete_result["status"] == "deleted"


@pytest.mark.asyncio
async def test_search_files():
    """Test search_files tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "search_files",
            {"account_id": account_info["account_id"], "query": "test", "limit": 5},
        )
        assert not result.isError
        search_results = parse_result(result)
        assert search_results is not None


@pytest.mark.asyncio
async def test_search_emails():
    """Test search_emails tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "search_emails",
            {"account_id": account_info["account_id"], "query": "test", "limit": 5},
        )
        assert not result.isError
        search_results = parse_result(result)
        assert search_results is not None


@pytest.mark.asyncio
async def test_search_events():
    """Test search_events tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "search_events",
            {"account_id": account_info["account_id"], "query": "meeting", "limit": 5},
        )
        assert not result.isError
        search_results = parse_result(result)
        assert search_results is not None


@pytest.mark.asyncio
async def test_search_contacts():
    """Test search_contacts tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "search_contacts",
            {
                "account_id": account_info["account_id"],
                "query": account_info["email"].split("@")[0],
                "limit": 5,
            },
        )
        assert not result.isError
        search_results = parse_result(result)
        assert search_results is not None


@pytest.mark.asyncio
async def test_send_email():
    """Test send_email tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        await asyncio.sleep(2)

        result = await session.call_tool(
            "email_send",
            {
                "account_id": account_info["account_id"],
                "to": account_info["email"],
                "subject": f"MCP Test Send Email V3 {datetime.now(timezone.utc).isoformat()}",
                "body": "This is a test email sent via send_email tool v3",
                "confirm": True,
            },
        )
        assert not result.isError
        sent_result = parse_result(result)
        assert sent_result is not None
        assert sent_result["status"] == "sent"


@pytest.mark.asyncio
async def test_unified_search():
    """Test unified_search tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "search_unified",
            {
                "account_id": account_info["account_id"],
                "query": "test",
                "entity_types": ["message"],
                "limit": 10,
            },
        )
        assert not result.isError
        search_results = parse_result(result)
        assert search_results is not None
        assert isinstance(search_results, dict)
        if "message" in search_results:
            assert isinstance(search_results["message"], list)


@pytest.mark.asyncio
async def test_list_files():
    """Test list_files tool"""
    async for session in get_session():
        account_info = await get_account_info(session)
        result = await session.call_tool(
            "file_list", {"account_id": account_info["account_id"]}
        )
        assert not result.isError
        files = parse_result(result)
        assert files is not None
        if len(files) > 0:
            assert "id" in files[0]
            assert "name" in files[0]
            assert "type" in files[0]


@pytest.mark.asyncio
async def test_get_file():
    """Test get_file tool"""
    import tempfile

    async for session in get_session():
        account_info = await get_account_info(session)
        test_content = "Test file content"
        test_filename = (
            f"/mcp-test-get-v3-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as local_file:
            local_file.write(test_content)
            local_file_path = local_file.name
        try:
            create_result = await session.call_tool(
                "file_create",
                {
                    "account_id": account_info["account_id"],
                    "onedrive_path": test_filename,
                    "local_file_path": local_file_path,
                },
            )
        finally:
            if os.path.exists(local_file_path):
                os.unlink(local_file_path)
        file_data = parse_result(create_result)
        file_id = file_data["id"]
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        os.unlink(tmp_path)
        try:
            result = await session.call_tool(
                "file_get",
                {
                    "file_id": file_id,
                    "account_id": account_info["account_id"],
                    "download_path": tmp_path,
                },
            )
            assert not result.isError
            with open(tmp_path, "r") as f:
                assert f.read() == test_content
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        await session.call_tool(
            "file_delete",
            {
                "file_id": file_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )


@pytest.mark.asyncio
async def test_create_file():
    """Test create_file tool"""
    import tempfile

    async for session in get_session():
        account_info = await get_account_info(session)
        test_content = (
            f"MCP Integration Test V3\nTimestamp: {datetime.now().isoformat()}"
        )
        test_filename = (
            f"/mcp-test-create-v3-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as local_file:
            local_file.write(test_content)
            local_file_path = local_file.name
        try:
            result = await session.call_tool(
                "file_create",
                {
                    "account_id": account_info["account_id"],
                    "onedrive_path": test_filename,
                    "local_file_path": local_file_path,
                },
            )
        finally:
            if os.path.exists(local_file_path):
                os.unlink(local_file_path)
        assert not result.isError
        upload_result = parse_result(result)
        assert upload_result is not None
        assert "id" in upload_result
        file_id = upload_result["id"]
        await session.call_tool(
            "file_delete",
            {
                "file_id": file_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )


@pytest.mark.asyncio
async def test_update_file():
    """Test update_file tool"""
    import tempfile

    async for session in get_session():
        account_info = await get_account_info(session)
        test_content = "Original content"
        test_filename = (
            f"/mcp-test-update-v3-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as local_file:
            local_file.write(test_content)
            local_file_path = local_file.name
        try:
            create_result = await session.call_tool(
                "file_create",
                {
                    "account_id": account_info["account_id"],
                    "onedrive_path": test_filename,
                    "local_file_path": local_file_path,
                },
            )
        finally:
            if os.path.exists(local_file_path):
                os.unlink(local_file_path)
        file_data = parse_result(create_result)
        file_id = file_data["id"]
        updated_content = f"Updated content at {datetime.now().isoformat()}"
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as updated_file:
            updated_file.write(updated_content)
            updated_file_path = updated_file.name
        try:
            result = await session.call_tool(
                "file_update",
                {
                    "account_id": account_info["account_id"],
                    "file_id": file_id,
                    "local_file_path": updated_file_path,
                },
            )
        finally:
            if os.path.exists(updated_file_path):
                os.unlink(updated_file_path)
        assert not result.isError
        await session.call_tool(
            "file_delete",
            {
                "file_id": file_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )


@pytest.mark.asyncio
async def test_delete_file():
    """Test delete_file tool"""
    import tempfile

    async for session in get_session():
        account_info = await get_account_info(session)
        test_content = "File to be deleted"
        test_filename = (
            f"/mcp-test-delete-v3-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as local_file:
            local_file.write(test_content)
            local_file_path = local_file.name
        try:
            create_result = await session.call_tool(
                "file_create",
                {
                    "account_id": account_info["account_id"],
                    "onedrive_path": test_filename,
                    "local_file_path": local_file_path,
                },
            )
        finally:
            if os.path.exists(local_file_path):
                os.unlink(local_file_path)
        file_data = parse_result(create_result)
        file_id = file_data["id"]
        result = await session.call_tool(
            "file_delete",
            {
                "file_id": file_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
        assert not result.isError
        delete_result = parse_result(result)
        assert delete_result is not None
        assert delete_result["status"] == "deleted"


@pytest.mark.asyncio
async def test_get_attachment():
    """Test get_attachment tool"""
    import tempfile

    async for session in get_session():
        account_info = await get_account_info(session)
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, "test_file.txt")
        with open(temp_file_path, "w") as f:
            f.write("This is a test attachment content")
        try:
            draft_result = await session.call_tool(
                "email_create_draft",
                {
                    "account_id": account_info["account_id"],
                    "to": account_info["email"],
                    "subject": "MCP Test Email with Attachment V3",
                    "body": "This email contains a test attachment",
                    "attachments": temp_file_path,
                },
            )
        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        assert not draft_result.isError
        draft_data = parse_result(draft_result)
        email_id = draft_data["id"]
        email_result = await session.call_tool(
            "email_get",
            {"email_id": email_id, "account_id": account_info["account_id"]},
        )
        email_detail = parse_result(email_result)
        assert email_detail.get("attachments"), "Email should have attachments"
        attachment = email_detail["attachments"][0]
        tmp_fd, save_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        os.unlink(save_path)
        try:
            result = await session.call_tool(
                "email_get_attachment",
                {
                    "email_id": email_id,
                    "account_id": account_info["account_id"],
                    "attachment_id": attachment["id"],
                    "save_path": save_path,
                },
            )
            assert not result.isError
            assert os.path.exists(save_path)
            with open(save_path, "r") as f:
                assert f.read() == "This is a test attachment content"
        finally:
            if os.path.exists(save_path):
                os.unlink(save_path)
        await session.call_tool(
            "email_delete",
            {
                "email_id": email_id,
                "account_id": account_info["account_id"],
                "confirm": True,
            },
        )
