from typing import Any
from ..mcp_instance import mcp
from .. import graph
from ..validators import validate_limit, require_confirm, validate_microsoft_graph_id


def _list_mail_folders_impl(
    account_id: str,
    parent_folder_id: str | None = None,
    include_hidden: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Internal implementation for listing mail folders"""
    if parent_folder_id:
        endpoint = f"/me/mailFolders/{parent_folder_id}/childFolders"
    else:
        endpoint = "/me/mailFolders"

    page_size = limit if limit is not None else 250
    params = {
        "$select": "id,displayName,childFolderCount,unreadItemCount,totalItemCount,parentFolderId,isHidden",
        "$top": page_size,
    }

    if include_hidden:
        params["includeHiddenFolders"] = "true"

    folders = list(
        graph.request_paginated(endpoint, account_id, params=params, limit=limit)
    )

    return folders


# emailfolders_list
@mcp.tool(
    name="emailfolders_list",
    annotations={
        "title": "List Email Folders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "safe"},
)
def emailfolders_list(
    account_id: str,
    parent_folder_id: str | None = None,
    include_hidden: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """📖 List mail folders from mailbox (read-only, safe for unsupervised use)

    Returns root folders or child folders of a specific parent with metadata
    including unread counts and child folder information.

    Args:
        account_id: Microsoft account ID
        parent_folder_id: If None, lists root folders. If provided, lists child folders.
        include_hidden: Whether to include hidden folders (default: False)
        limit: Maximum number of folders to return (1-250, default: 100)

    Returns:
        List of folder objects with: id, displayName, childFolderCount,
        unreadItemCount, totalItemCount, parentFolderId, isHidden
    """
    limit = validate_limit(limit, 1, 250, "limit")
    return _list_mail_folders_impl(account_id, parent_folder_id, include_hidden, limit)


# emailfolders_get
@mcp.tool(
    name="emailfolders_get",
    annotations={
        "title": "Get Email Folder",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "safe"},
)
def emailfolders_get(
    folder_id: str,
    account_id: str,
) -> dict[str, Any]:
    """📖 Get detailed information about a specific mail folder (read-only, safe for unsupervised use)

    Returns complete folder metadata including counts and hierarchy information.

    Args:
        folder_id: The folder ID to retrieve
        account_id: Microsoft account ID

    Returns:
        Folder object with full metadata including id, displayName,
        childFolderCount, unreadItemCount, totalItemCount
    """
    result = graph.request("GET", f"/me/mailFolders/{folder_id}", account_id)
    if not result:
        raise ValueError(f"Mail folder with ID {folder_id} not found")
    return result


# emailfolders_get_tree
@mcp.tool(
    name="emailfolders_get_tree",
    annotations={
        "title": "Get Email Folder Tree",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "safe"},
)
def emailfolders_get_tree(
    account_id: str,
    parent_folder_id: str | None = None,
    max_depth: int = 10,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """📖 Recursively build a tree of mail folders (read-only, safe for unsupervised use)

    Returns a hierarchical tree structure showing all folders and their nested children.
    Useful for understanding mailbox folder organization.

    Args:
        account_id: Microsoft account ID
        parent_folder_id: Root folder to start from (None = root)
        max_depth: Maximum recursion depth to prevent infinite loops (1-25, default: 10)
        include_hidden: Whether to include hidden folders (default: False)

    Returns:
        Nested tree structure with folders and their children
    """
    max_depth = validate_limit(max_depth, 1, 25, "max_depth")

    def _build_folder_tree(
        folder_id: str | None, current_depth: int
    ) -> list[dict[str, Any]]:
        """Internal recursive helper to build folder tree"""
        if current_depth >= max_depth:
            return []

        # Get folders at this level
        folders = _list_mail_folders_impl(
            account_id=account_id,
            parent_folder_id=folder_id,
            include_hidden=include_hidden,
            limit=None,
        )

        result = []
        for folder in folders:
            folder_node = {
                "id": folder["id"],
                "displayName": folder.get("displayName", ""),
                "childFolderCount": folder.get("childFolderCount", 0),
                "unreadItemCount": folder.get("unreadItemCount", 0),
                "totalItemCount": folder.get("totalItemCount", 0),
                "parentFolderId": folder.get("parentFolderId"),
                "isHidden": folder.get("isHidden", False),
                "children": [],
            }

            # Recursively get children if this folder has child folders
            if folder.get("childFolderCount", 0) > 0:
                folder_node["children"] = _build_folder_tree(
                    folder["id"], current_depth + 1
                )

            result.append(folder_node)

        return result

    # Build tree starting from specified parent or root
    tree_data = _build_folder_tree(parent_folder_id, 0)

    return {
        "root_folder_id": parent_folder_id,
        "max_depth": max_depth,
        "folders": tree_data,
    }


# emailfolders_create
@mcp.tool(
    name="emailfolders_create",
    annotations={
        "title": "Create Email Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "moderate"},
)
def emailfolders_create(
    display_name: str,
    account_id: str,
    parent_folder_id: str | None = None,
) -> dict[str, Any]:
    """✏️ Create a new mail folder (requires user confirmation recommended)

    Creates a new mail folder in the mailbox, either at the root level or
    as a child of an existing folder.

    Args:
        display_name: Name for the new folder
        account_id: Microsoft account ID
        parent_folder_id: Parent folder ID (None = root level)

    Returns:
        Created folder object with id, displayName, and other metadata

    Raises:
        ValueError: If display_name is empty or parent_folder_id is invalid
    """
    if not display_name or not display_name.strip():
        raise ValueError("display_name cannot be empty")

    display_name = display_name.strip()

    # Validate parent folder if provided
    if parent_folder_id:
        parent_folder_id = validate_microsoft_graph_id(
            parent_folder_id, "parent_folder_id"
        )
        endpoint = f"/me/mailFolders/{parent_folder_id}/childFolders"
    else:
        endpoint = "/me/mailFolders"

    payload = {"displayName": display_name}

    result = graph.request("POST", endpoint, account_id, json=payload)

    if not result:
        raise ValueError("Failed to create mail folder")

    return result


# emailfolders_rename
@mcp.tool(
    name="emailfolders_rename",
    annotations={
        "title": "Rename Email Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "moderate"},
)
def emailfolders_rename(
    folder_id: str,
    new_display_name: str,
    account_id: str,
) -> dict[str, Any]:
    """✏️ Rename a mail folder (requires user confirmation recommended)

    Updates the display name of an existing mail folder.

    Args:
        folder_id: The folder ID to rename
        new_display_name: New name for the folder
        account_id: Microsoft account ID

    Returns:
        Updated folder object with new displayName

    Raises:
        ValueError: If folder_id is invalid or new_display_name is empty
    """
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    if not new_display_name or not new_display_name.strip():
        raise ValueError("new_display_name cannot be empty")

    new_display_name = new_display_name.strip()

    payload = {"displayName": new_display_name}

    result = graph.request(
        "PATCH", f"/me/mailFolders/{folder_id}", account_id, json=payload
    )

    if not result:
        raise ValueError(f"Failed to rename mail folder {folder_id}")

    return result


# emailfolders_move
@mcp.tool(
    name="emailfolders_move",
    annotations={
        "title": "Move Email Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "moderate"},
)
def emailfolders_move(
    folder_id: str,
    destination_folder_id: str,
    account_id: str,
) -> dict[str, Any]:
    """✏️ Move a mail folder to a different parent (requires user confirmation recommended)

    Moves a mail folder to become a child of a different parent folder.

    Args:
        folder_id: The folder ID to move
        destination_folder_id: The destination parent folder ID
        account_id: Microsoft account ID

    Returns:
        Updated folder object with new parentFolderId

    Raises:
        ValueError: If folder_id or destination_folder_id is invalid
    """
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")
    destination_folder_id = validate_microsoft_graph_id(
        destination_folder_id, "destination_folder_id"
    )

    payload = {"parentFolderId": destination_folder_id}

    result = graph.request(
        "PATCH", f"/me/mailFolders/{folder_id}", account_id, json=payload
    )

    if not result:
        raise ValueError(f"Failed to move mail folder {folder_id}")

    return result


# emailfolders_delete
@mcp.tool(
    name="emailfolders_delete",
    annotations={
        "title": "Delete Email Folder",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "critical"},
)
def emailfolders_delete(
    folder_id: str,
    account_id: str,
    confirm: bool = False,
) -> dict[str, str]:
    """🔴 Delete a mail folder permanently (always require user confirmation)

    WARNING: This action permanently deletes the folder and all its contents
    (emails and subfolders) and cannot be undone.

    Args:
        folder_id: The folder ID to delete
        account_id: Microsoft account ID
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation

    Raises:
        ValueError: If folder_id is invalid or confirm is False
    """
    require_confirm(confirm, "delete mail folder")
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    graph.request("DELETE", f"/me/mailFolders/{folder_id}", account_id)

    return {"status": "deleted", "folder_id": folder_id}


# emailfolders_mark_all_as_read
@mcp.tool(
    name="emailfolders_mark_all_as_read",
    annotations={
        "title": "Mark All Emails in Folder as Read",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "moderate"},
)
def emailfolders_mark_all_as_read(
    folder_id: str,
    account_id: str,
) -> dict[str, Any]:
    """✏️ Mark all messages in a folder as read (requires user confirmation recommended)

    Updates all messages in the specified folder to mark them as read.
    This operation may take time for folders with many messages.

    Args:
        folder_id: The folder ID containing messages to mark as read
        account_id: Microsoft account ID

    Returns:
        Status confirmation with count of messages updated

    Raises:
        ValueError: If folder_id is invalid
    """
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    # Get all messages in the folder
    endpoint = f"/me/mailFolders/{folder_id}/messages"
    params = {
        "$select": "id,isRead",
        "$filter": "isRead eq false",
        "$top": 999,
    }

    messages = list(graph.request_paginated(endpoint, account_id, params=params))

    # Mark each message as read
    update_count = 0
    for message in messages:
        if not message.get("isRead", False):
            try:
                graph.request(
                    "PATCH",
                    f"/me/messages/{message['id']}",
                    account_id,
                    json={"isRead": True},
                )
                update_count += 1
            except Exception:
                # Log error but continue with other messages
                pass

    return {
        "status": "completed",
        "folder_id": folder_id,
        "messages_marked_read": update_count,
    }


# emailfolders_empty
@mcp.tool(
    name="emailfolders_empty",
    annotations={
        "title": "Empty Email Folder",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "emailfolders", "safety_level": "critical"},
)
def emailfolders_empty(
    folder_id: str,
    account_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """🔴 Delete all messages in a folder (always require user confirmation)

    WARNING: This action permanently deletes all messages in the folder
    and cannot be undone. The folder itself remains but all messages
    are permanently deleted.

    Args:
        folder_id: The folder ID to empty
        account_id: Microsoft account ID
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation with count of messages deleted

    Raises:
        ValueError: If folder_id is invalid or confirm is False
    """
    require_confirm(confirm, "empty mail folder")
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    # Get all messages in the folder
    endpoint = f"/me/mailFolders/{folder_id}/messages"
    params = {
        "$select": "id",
        "$top": 999,
    }

    messages = list(graph.request_paginated(endpoint, account_id, params=params))

    # Delete each message
    delete_count = 0
    for message in messages:
        try:
            graph.request("DELETE", f"/me/messages/{message['id']}", account_id)
            delete_count += 1
        except Exception:
            # Log error but continue with other messages
            pass

    return {
        "status": "completed",
        "folder_id": folder_id,
        "messages_deleted": delete_count,
    }
