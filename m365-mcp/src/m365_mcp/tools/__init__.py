# Import all tool functions from the tools package
# This allows importing specific functions like: from tools import email_list, account_list

# Import the mcp instance from parent
from ..mcp_instance import mcp

# # Account management functions
# from .account import (
#     account_list,
#     account_authenticate,
#     account_complete_auth,
# )

# # Calendar functions
# from .calendar import (
#     calendar_get_event,
#     calendar_create_event,
#     calendar_update_event,
#     calendar_delete_event,
#     calendar_respond_event,
#     calendar_check_availability,
# )

# # Contact management functions
# from .contact import (
#     contact_list,
#     contact_get,
#     contact_create,
#     contact_update,
#     contact_delete,
# )

# Email folder management functions
from .email_folders import (
    emailfolders_list,
    emailfolders_get,
    emailfolders_get_tree,
)

# Email rule management functions
from .email_rules import (
    emailrules_list,
    emailrules_get,
    emailrules_create,
    emailrules_update,
    emailrules_delete,
    emailrules_move_top,
    emailrules_move_bottom,
    emailrules_move_up,
    emailrules_move_down,
)

# Email management functions
from .email import (
    email_list,
    email_get,
    email_create_draft,
    email_send,
    email_update,
    email_delete,
    email_move,
    email_reply,
    email_get_attachment,
)

# # File management functions
# from .file import (
#     file_list,
#     file_get,
#     file_create,
#     file_update,
#     file_delete,
# )

# # Folder management functions
# from .folder import (
#     folder_list,
#     folder_get,
#     folder_get_tree,
# )

# # Search functions
# from .search import (
#     search_files,
#     search_emails,
#     search_events,
#     search_contacts,
#     search_unified,
# )

# # Server functions
# from .server import (
#     server_get_version,
# )

# Cache management functions
from .cache_tools import (
    cache_task_get_status,
    cache_task_list,
    cache_get_stats,
    cache_invalidate,
    cache_warming_status,
)

# Common constants (using from email.py as they are consistent across files)
from .email import FOLDERS

# Export all functions and mcp instance for easy access
__all__ = [
    # MCP instance
    "mcp",
    # # Account functions
    # "account_list",
    # "account_authenticate",
    # "account_complete_auth",
    # # Calendar functions
    # "calendar_get_event",
    # "calendar_create_event",
    # "calendar_update_event",
    # "calendar_delete_event",
    # "calendar_respond_event",
    # "calendar_check_availability",
    # # Contact functions
    # "contact_list",
    # "contact_get",
    # "contact_create",
    # "contact_update",
    # "contact_delete",
    # Email folder functions
    "emailfolders_list",
    "emailfolders_get",
    "emailfolders_get_tree",
    # Email rule functions
    "emailrules_list",
    "emailrules_get",
    "emailrules_create",
    "emailrules_update",
    "emailrules_delete",
    "emailrules_move_top",
    "emailrules_move_bottom",
    "emailrules_move_up",
    "emailrules_move_down",
    # Email functions
    "email_list",
    "email_get",
    "email_create_draft",
    "email_send",
    "email_update",
    "email_delete",
    "email_move",
    "email_reply",
    "email_get_attachment",
    # # File functions
    # "file_list",
    # "file_get",
    # "file_create",
    # "file_update",
    # "file_delete",
    # # Folder functions
    # "folder_list",
    # "folder_get",
    # "folder_get_tree",
    # # Search functions
    # "search_files",
    # "search_emails",
    # "search_events",
    # "search_contacts",
    # "search_unified",
    # # Server functions
    # "server_get_version",
    # Cache functions
    "cache_task_get_status",
    "cache_task_list",
    "cache_get_stats",
    "cache_invalidate",
    "cache_warming_status",
    # Constants
    "FOLDERS",
]
