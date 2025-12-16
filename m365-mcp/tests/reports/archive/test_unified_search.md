# Test Report: test_unified_search

## Test Status: FAILED

## Test Purpose
Test the `search_unified` tool functionality to perform unified searches across multiple Microsoft Graph entities.

## Failure Analysis

### Primary Issue: Microsoft Graph API Error
**Error Message:** `Client error '400 Bad Request' for url 'https://graph.microsoft.com/v1.0/search/query'`

**Root Cause:** The test fails because the Microsoft Graph API returns a 400 Bad Request error when attempting to perform a unified search. This indicates that the search request is malformed or the unified search functionality is not properly configured.

### Technical Details
- **Test Location:** `tests/test_integration.py::test_unified_search`
- **Failure Type:** HTTPStatusError - 400 Bad Request
- **API Endpoint:** `https://graph.microsoft.com/v1.0/search/query`
- **Impact:** The unified search functionality cannot be tested due to API request issues

### Test Parameters
The test was attempting to call `search_unified` with:
- `account_id`: User's account identifier
- `query`: "test" (search term)
- `entity_types`: ["message"] (search only in email messages)
- `limit`: 10 (maximum number of results)

### API Request Details
The error occurs in the `search_query` method in `graph.py` at line 302, where the HTTP request is made to the Microsoft Graph unified search endpoint.

### Unified Search Requirements
The Microsoft Graph unified search API typically requires:
- Proper authentication and permissions
- Valid search query parameters
- Correct entity type specifications
- Proper request formatting for multi-entity searches

### Likely Causes
1. **Missing Permissions:** The application may not have the required permissions for unified search functionality
2. **Invalid Search Parameters:** The search request parameters may be malformed or invalid
3. **API Configuration Issue:** The unified search endpoint may not be properly configured
4. **Query Format Issue:** The search query format may not match what the API expects
5. **Tenant Configuration:** The tenant may not have unified search functionality enabled
6. **Entity Type Issue:** The specified entity types may not be valid or supported

### Recommendations
1. **Check Permissions:** Verify that the application has the required permissions for unified search functionality
2. **Review API Documentation:** Check the Microsoft Graph unified search API documentation for correct parameter format
3. **Debug Request:** Add logging to see the exact request being sent to the API
4. **Test with Different Entity Types:** Try with different or additional entity types
5. **Verify Tenant Settings:** Check if unified search functionality is enabled in the tenant
6. **Add Error Handling:** Improve error handling to provide more detailed error information

### Additional Context
The unified search functionality is a powerful feature that allows searching across multiple Microsoft Graph entities (emails, files, events, contacts) in a single request. The test was attempting to:
1. Search for the term "test" across email messages
2. Limit results to 10 items
3. Verify that the search returns appropriate results from the specified entity types

The failure prevents testing of the unified search functionality, which is essential for providing comprehensive search capabilities across all Microsoft 365 services.

### Related Issues
This same 400 Bad Request error pattern appears in other search-related tests (search_files, search_emails, search_events), suggesting a systemic issue with the search API implementation or configuration. All search functionality appears to be affected by the same underlying issue.

### Unified Search Specific Considerations
Unified search may have additional requirements:
- Proper permissions for all entity types being searched
- Correct entity type specifications
- Proper request formatting for multi-entity queries
- Tenant-level search configuration
- Search indexing requirements for different entity types
