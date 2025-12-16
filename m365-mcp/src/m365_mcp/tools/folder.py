from typing import Any
from datetime import datetime, timezone
from ..mcp_instance import mcp
from .. import graph
from ..validators import (
    validate_limit,
    validate_onedrive_path,
    validate_microsoft_graph_id,
    require_confirm,
)
from ..cache_config import generate_cache_key
from .cache_tools import get_cache_manager


def _list_folders_impl(
    account_id: str,
    path: str | None = "/",
    folder_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Internal implementation for listing OneDrive folders"""
    if folder_id:
        endpoint = f"/me/drive/items/{folder_id}/children"
    else:
        normalised_path = validate_onedrive_path(path or "/", "path")
        if normalised_path == "/":
            endpoint = "/me/drive/root/children"
        else:
            endpoint = f"/me/drive/root:{normalised_path}:/children"

    page_size = limit if limit is not None else 500
    params = {
        "$top": page_size,
        "$select": "id,name,folder,parentReference,size,lastModifiedDateTime",
    }

    items = list(
        graph.request_paginated(endpoint, account_id, params=params, limit=limit)
    )

    # Filter to only return folders
    folders = []
    for item in items:
        if "folder" in item:
            folders.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "childCount": item.get("folder", {}).get("childCount", 0),
                    "path": item.get("parentReference", {}).get("path", ""),
                    "parentId": item.get("parentReference", {}).get("id"),
                    "modified": item.get("lastModifiedDateTime"),
                }
            )

    return folders


# folder_list
@mcp.tool(
    name="folder_list",
    annotations={
        "title": "List Folders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "safe"},
)
def folder_list(
    account_id: str,
    path: str = "/",
    folder_id: str | None = None,
    limit: int = 50,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """📖 List only folders (not files) in OneDrive (read-only, safe for unsupervised use)

    Returns folders with child counts and hierarchy information.

    Caching: Results are cached for 15 minutes (fresh) / 1 hour (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        account_id: Microsoft account ID
        path: Path to list folders from (e.g., "/Documents", default: "/")
        folder_id: Direct folder ID (takes precedence over path)
        limit: Maximum folders to return (1-500, default: 50)
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        Dictionary with:
        - folders: List of folder objects with id, name, childCount, path, parentId
        - _cache_status: Cache state (fresh/stale/miss)
        - _cached_at: When data was cached (ISO format)
    """
    limit = validate_limit(limit, 1, 500, "limit")

    # Generate cache key from parameters
    cache_params = {
        "path": path,
        "folder_id": folder_id,
        "limit": limit,
    }
    generate_cache_key(account_id, "folder_list", cache_params)

    # Try to get from cache if enabled and not forcing refresh
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "folder_list", cache_params
            )

            if cached_result:
                data, state = cached_result
                # Return cached data with cache status
                return {
                    "folders": data["folders"],
                    "_cache_status": state.value,
                    "_cached_at": data.get("_cached_at"),
                }
        except Exception:
            # If cache fails, continue to API call
            pass

    # Fetch from API
    folders = _list_folders_impl(
        account_id=account_id,
        path=path,
        folder_id=folder_id,
        limit=limit,
    )

    result = {
        "folders": folders,
        "_cache_status": "miss",  # Fresh from API
        "_cached_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store in cache if enabled
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(account_id, "folder_list", cache_params, result)
        except Exception:
            # If cache storage fails, still return the result
            pass

    return result


# folder_get
@mcp.tool(
    name="folder_get",
    annotations={
        "title": "Get Folder",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "safe"},
)
def folder_get(
    account_id: str,
    folder_id: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """📖 Get metadata for a specific OneDrive folder (read-only, safe for unsupervised use)

    Returns folder details including child count and web URL.

    Args:
        account_id: Microsoft account ID
        folder_id: Folder ID (takes precedence if provided)
        path: Folder path (e.g., "/Documents/Projects")

    Returns:
        Folder metadata including childCount, webUrl, and parent info
    """
    if not folder_id and not path:
        raise ValueError("Either folder_id or path must be provided")

    if folder_id:
        endpoint = f"/me/drive/items/{folder_id}"
    else:
        normalised_path = validate_onedrive_path(path or "/", "path")
        if normalised_path == "/":
            endpoint = "/me/drive/root"
        else:
            endpoint = f"/me/drive/root:{normalised_path}"

    result = graph.request("GET", endpoint, account_id)
    if not result:
        raise ValueError("Folder not found")

    # Validate it's actually a folder
    if "folder" not in result:
        raise ValueError("Item at specified location is not a folder")

    return {
        "id": result["id"],
        "name": result["name"],
        "childCount": result.get("folder", {}).get("childCount", 0),
        "path": result.get("parentReference", {}).get("path", ""),
        "parentId": result.get("parentReference", {}).get("id"),
        "modified": result.get("lastModifiedDateTime"),
        "webUrl": result.get("webUrl"),
    }


# folder_get_tree
@mcp.tool(
    name="folder_get_tree",
    annotations={
        "title": "Get Folder Tree",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "safe"},
)
def folder_get_tree(
    account_id: str,
    path: str = "/",
    folder_id: str | None = None,
    max_depth: int = 10,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """📖 Recursively build a tree of OneDrive folders (read-only, safe for unsupervised use)

    Returns a hierarchical tree structure showing all folders and nested subfolders.
    Useful for understanding OneDrive folder organization.

    Caching: Results are cached for 30 minutes (fresh) / 2 hours (stale).
    Use force_refresh=True to bypass cache and fetch fresh data.

    Args:
        account_id: Microsoft account ID
        path: Starting path (default: "/")
        folder_id: Starting folder ID (takes precedence over path)
        max_depth: Maximum recursion depth (1-25, default: 10)
        use_cache: Whether to use cached data if available (default: True)
        force_refresh: Force refresh from API, bypassing cache (default: False)

    Returns:
        Nested tree structure with folders and their children, including:
        - _cache_status: Cache state (fresh/stale/miss)
        - _cached_at: When data was cached (ISO format)
    """
    max_depth = validate_limit(max_depth, 1, 25, "max_depth")

    # Generate cache key from parameters
    cache_params = {
        "path": path,
        "folder_id": folder_id,
        "max_depth": max_depth,
    }
    generate_cache_key(account_id, "folder_get_tree", cache_params)

    # Try to get from cache if enabled and not forcing refresh
    if use_cache and not force_refresh:
        try:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_cached(
                account_id, "folder_get_tree", cache_params
            )

            if cached_result:
                data, state = cached_result
                # Return cached data with cache status
                data["_cache_status"] = state.value
                return data
        except Exception:
            # If cache fails, continue to API call
            pass

    def _build_drive_folder_tree(
        item_id: str | None, item_path: str | None, current_depth: int
    ) -> list[dict[str, Any]]:
        """Internal recursive helper to build OneDrive folder tree"""
        if current_depth >= max_depth:
            return []

        # Get folders at this level
        try:
            folders = _list_folders_impl(
                account_id=account_id,
                path=item_path if not item_id else None,
                folder_id=item_id,
                limit=None,
            )
        except Exception:
            # Log error but don't fail entire tree operation
            # Return empty list to stop recursion on this branch
            return []

        result = []
        for folder in folders:
            folder_node = {
                "id": folder["id"],
                "name": folder["name"],
                "childCount": folder.get("childCount", 0),
                "path": folder.get("path", ""),
                "parentId": folder.get("parentId"),
                "modified": folder.get("modified"),
                "children": [],
            }

            # Always recurse to check for subfolders
            # The API call will return empty list if no subfolders exist
            # This is more efficient than checking childCount which includes files
            folder_node["children"] = _build_drive_folder_tree(
                folder["id"], None, current_depth + 1
            )

            result.append(folder_node)

        return result

    # Build tree starting from specified location
    if folder_id:
        start_id = folder_id
        start_path: str | None = None
    else:
        start_id = None
        start_path = validate_onedrive_path(path or "/", "path")

    tree_data = _build_drive_folder_tree(start_id, start_path, 0)

    result = {
        "root_folder_id": folder_id,
        "root_path": start_path if start_path is not None else None,
        "max_depth": max_depth,
        "folders": tree_data,
        "_cache_status": "miss",  # Fresh from API
        "_cached_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store in cache if enabled
    if use_cache:
        try:
            cache_manager = get_cache_manager()
            cache_manager.set_cached(
                account_id, "folder_get_tree", cache_params, result
            )
        except Exception:
            # If cache storage fails, still return the result
            pass

    return result


# folder_create
@mcp.tool(
    name="folder_create",
    annotations={
        "title": "Create OneDrive Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "moderate"},
)
def folder_create(
    name: str,
    account_id: str,
    parent_folder_id: str | None = None,
) -> dict[str, Any]:
    """✏️ Create a new OneDrive folder (requires user confirmation recommended)

    Creates a new folder in OneDrive, either at the root level or
    as a child of an existing folder.

    Args:
        name: Name for the new folder
        account_id: Microsoft account ID
        parent_folder_id: Parent folder ID (None = root level)

    Returns:
        Created folder object with id, name, and other metadata

    Raises:
        ValueError: If name is empty or parent_folder_id is invalid
    """
    if not name or not name.strip():
        raise ValueError("name cannot be empty")

    name = name.strip()

    if parent_folder_id:
        parent_folder_id = validate_microsoft_graph_id(
            parent_folder_id, "parent_folder_id"
        )
        endpoint = f"/me/drive/items/{parent_folder_id}/children"
    else:
        endpoint = "/me/drive/root/children"

    payload = {
        "name": name,
        "folder": {},  # This tells Graph API to create a folder
        "@microsoft.graph.conflictBehavior": "rename",
    }

    result = graph.request("POST", endpoint, account_id, json=payload)
    if not result:
        raise ValueError("Failed to create folder")
    return result


# folder_delete
@mcp.tool(
    name="folder_delete",
    annotations={
        "title": "Delete OneDrive Folder",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "critical"},
)
def folder_delete(
    folder_id: str,
    account_id: str,
    confirm: bool = False,
) -> dict[str, str]:
    """🔴 Delete an OneDrive folder permanently (always require user confirmation)

    WARNING: This action permanently deletes the folder and all its contents
    (files and subfolders) and cannot be undone.

    Args:
        folder_id: The folder ID to delete
        account_id: Microsoft account ID
        confirm: Must be True to confirm deletion (prevents accidents)

    Returns:
        Status confirmation

    Raises:
        ValueError: If folder_id is invalid or confirm is False
    """
    require_confirm(confirm, "delete OneDrive folder")
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    graph.request("DELETE", f"/me/drive/items/{folder_id}", account_id)

    return {"status": "deleted", "folder_id": folder_id}


# folder_rename
@mcp.tool(
    name="folder_rename",
    annotations={
        "title": "Rename OneDrive Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "moderate"},
)
def folder_rename(
    folder_id: str,
    new_name: str,
    account_id: str,
) -> dict[str, Any]:
    """✏️ Rename an OneDrive folder (requires user confirmation recommended)

    Updates the name of an existing OneDrive folder.

    Args:
        folder_id: The folder ID to rename
        new_name: New name for the folder
        account_id: Microsoft account ID

    Returns:
        Updated folder object with new name

    Raises:
        ValueError: If folder_id is invalid or new_name is empty
    """
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")

    if not new_name or not new_name.strip():
        raise ValueError("new_name cannot be empty")

    new_name = new_name.strip()

    payload = {"name": new_name}

    result = graph.request(
        "PATCH", f"/me/drive/items/{folder_id}", account_id, json=payload
    )
    if not result:
        raise ValueError("Failed to rename folder")

    return result


# folder_move
@mcp.tool(
    name="folder_move",
    annotations={
        "title": "Move OneDrive Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
    meta={"category": "folder", "safety_level": "moderate"},
)
def folder_move(
    folder_id: str,
    destination_folder_id: str,
    account_id: str,
) -> dict[str, Any]:
    """✏️ Move an OneDrive folder to a different parent (requires user confirmation recommended)

    Moves a folder to become a child of a different parent folder.

    Args:
        folder_id: The folder ID to move
        destination_folder_id: The destination parent folder ID
        account_id: Microsoft account ID

    Returns:
        Updated folder object with new parentReference

    Raises:
        ValueError: If folder_id or destination_folder_id is invalid
    """
    folder_id = validate_microsoft_graph_id(folder_id, "folder_id")
    destination_folder_id = validate_microsoft_graph_id(
        destination_folder_id, "destination_folder_id"
    )

    payload = {"parentReference": {"id": destination_folder_id}}

    result = graph.request(
        "PATCH", f"/me/drive/items/{folder_id}", account_id, json=payload
    )
    if not result:
        raise ValueError("Failed to move folder")

    return result
