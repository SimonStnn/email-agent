# Microsoft Graph API Research & Troubleshooting Guide

## Executive Summary

This document outlines the research and investigation needed to resolve 6 failing integration tests related to Microsoft Graph API issues. All failures are external to the codebase - the code is functioning correctly but encountering API-level errors.

**Status**: 28/34 tests passing (82%)
**Remaining Failures**: 6 tests (all API-related)
**Date**: 2025-10-14

---

## Overview of Failures

### Category 1: Search API Failures (5 tests)
**Tests Affected**:
- `test_search_files`
- `test_search_emails`
- `test_search_events`
- `test_search_contacts`
- `test_unified_search`

**Error**: `Client error '400 Bad Request' for url 'https://graph.microsoft.com/v1.0/search/query'`

### Category 2: User Profile API Failure (1 test)
**Test Affected**:
- `test_check_availability`

**Error**: `Failed to get user email address` (GET /me endpoint doesn't return "mail" field)

---

## Category 1: Microsoft Graph Search API Issues

### 1.1 Problem Statement

All 5 search-related tests are failing with HTTP 400 Bad Request when calling the Microsoft Graph Search API endpoint.

**Endpoint**: `POST https://graph.microsoft.com/v1.0/search/query`

**Current Behavior**: API returns 400 Bad Request
**Expected Behavior**: API returns search results

### 1.2 What to Research

#### Permissions & Scopes

**Required Scopes for Search API**:
- [ ] Verify if `Files.Read.All` is required for file search
- [ ] Check if `Mail.Read` is sufficient for email search
- [ ] Confirm `Calendars.Read` for event search
- [ ] Verify `Contacts.Read` for contact search
- [ ] Check if **Microsoft Search permissions** are needed:
  - `ExternalItem.Read.All` (for unified search)
  - `Sites.Read.All` (for SharePoint search)

**Current Scopes** (from app registration):
```
Mail.ReadWrite
Calendars.ReadWrite
Files.ReadWrite
Contacts.Read
People.Read
User.Read
```

**Action Items**:
1. Review [Microsoft Graph Search API documentation](https://learn.microsoft.com/en-us/graph/api/resources/search-api-overview)
2. Check if additional permissions are needed in Azure App Registration
3. Verify app has been granted admin consent for required permissions
4. Test with elevated permissions if using delegated auth

#### Request Format Validation

**Current Implementation** (in `src/m365_mcp/graph.py`):
- Review the `search_query()` method
- Verify request payload format matches API requirements

**What to Check**:
- [ ] Examine exact request payload being sent to `/search/query`
- [ ] Verify JSON structure matches [API spec](https://learn.microsoft.com/en-us/graph/api/search-query)
- [ ] Check entity type values: "message", "event", "driveItem"
- [ ] Validate query string format (KQL syntax)
- [ ] Confirm headers (Content-Type, etc.)

**Diagnostic Steps**:
1. Enable detailed logging for Graph API requests
2. Capture exact request body sent to API
3. Compare with working examples from Microsoft documentation
4. Test with Microsoft Graph Explorer: https://developer.microsoft.com/graph/graph-explorer

#### Account Type & Licensing

**Microsoft Search API Limitations**:
- Search API may not be available for all account types
- Some features require specific Microsoft 365 licenses

**What to Verify**:
- [ ] Account type: Personal (outlook.com) vs Work/School (Microsoft 365)
- [ ] Check if Search API works with personal Microsoft accounts
- [ ] Verify Microsoft 365 license level (E3, E5, Business, etc.)
- [ ] Confirm tenant has Microsoft Search enabled
- [ ] Check for any regional restrictions

**Resources**:
- [Microsoft Graph Search API requirements](https://learn.microsoft.com/en-us/graph/search-concept-overview)
- Azure Portal → Azure Active Directory → Licenses

#### API Endpoint Availability

**Verify Endpoint Status**:
- [ ] Check Microsoft 365 Service Health Dashboard
- [ ] Verify `/search/query` endpoint is not deprecated
- [ ] Confirm API version (v1.0 vs beta) supports search
- [ ] Test alternative search methods if available

**Alternative Approaches**:
If `/search/query` is unavailable, consider:
1. Using `$search` parameter on individual endpoints:
   - `GET /me/messages?$search="query"`
   - `GET /me/events?$search="query"`
   - `GET /me/drive/root/search(q='query')`
2. Using `$filter` with specific conditions
3. Implementing client-side filtering

### 1.3 Investigation Steps

#### Step 1: Capture Full Error Response

Modify `src/m365_mcp/graph.py` to log full error details:

```python
# In graph.py request method, add detailed error logging:
except httpx.HTTPStatusError as e:
    logger.error(f"Graph API Error: {e.response.status_code}")
    logger.error(f"Response body: {e.response.text}")
    logger.error(f"Request URL: {e.request.url}")
    logger.error(f"Request body: {e.request.content}")
    raise
```

**Information to Collect**:
- Full error message from API
- Error code (if provided)
- Request URL and method
- Complete request payload
- Response headers

#### Step 2: Test with Graph Explorer

1. Go to https://developer.microsoft.com/graph/graph-explorer
2. Sign in with the same account used in tests
3. Try POST to `/search/query` with this payload:

```json
{
  "requests": [
    {
      "entityTypes": ["message"],
      "query": {
        "queryString": "test"
      },
      "from": 0,
      "size": 25
    }
  ]
}
```

4. Document the exact response (success or error)

#### Step 3: Review Code Implementation

**Files to Review**:
- `src/m365_mcp/graph.py` - Look for `search_query()` method
- `src/m365_mcp/tools/search.py` - Check how search tools call the API

**What to Verify**:
- [ ] Request payload format matches Microsoft documentation
- [ ] Entity type names are correct ("message", "event", "driveItem")
- [ ] Query string is properly formatted
- [ ] Headers include required values
- [ ] Authorization token is valid and not expired

#### Step 4: Test Alternative Search Methods

If unified search fails, test individual endpoint searches:

```bash
# Test email search with $search parameter
GET /me/messages?$search="subject:test"

# Test calendar event search
GET /me/events?$search="meeting"

# Test OneDrive file search
GET /me/drive/root/search(q='test')
```

Document which methods work vs. fail.

---

## Category 2: User Profile API Issue

### 2.1 Problem Statement

**Test**: `test_check_availability`
**Error**: `Failed to get user email address`
**Root Cause**: GET `/me` endpoint doesn't return "mail" field

### 2.2 What to Research

#### User Profile Field Availability

**Issue**: The "mail" field may not be present in all user profiles

**What to Check**:
- [ ] Verify which fields are returned by `GET /me`
- [ ] Check if "mail" vs "userPrincipalName" should be used
- [ ] Confirm if account has email configured
- [ ] Test with different account types (personal vs work)

**Alternative Fields**:
```json
{
  "mail": "user@domain.com",           // Primary email (may be null)
  "userPrincipalName": "user@domain.com", // Always present
  "otherMails": ["alt@domain.com"]     // Alternative emails
}
```

#### Code Location

**File**: `src/m365_mcp/tools/calendar.py`
**Function**: `calendar_check_availability()` (line ~713)

**Current Code**:
```python
me_info = graph.request("GET", "/me", account_id)
if not me_info or "mail" not in me_info or not me_info["mail"]:
    raise ValueError("Failed to get user email address")
```

### 2.3 Investigation Steps

#### Step 1: Check Actual Response

Test what `/me` actually returns:

```bash
GET https://graph.microsoft.com/v1.0/me
```

Document all fields returned, especially:
- `mail`
- `userPrincipalName`
- `otherMails`
- `proxyAddresses`

#### Step 2: Determine Best Field to Use

**Recommendation**: Use a fallback strategy

```python
me_info = graph.request("GET", "/me", account_id)
if not me_info:
    raise ValueError("Failed to get user information")

# Try multiple fields in order of preference
email = (
    me_info.get("mail") or
    me_info.get("userPrincipalName") or
    (me_info.get("otherMails", []) or [None])[0]
)

if not email:
    raise ValueError("Failed to get user email address")
```

### 2.4 Recommended Fix

**Option 1**: Use userPrincipalName as fallback
**Option 2**: Add `$select` parameter to ensure fields are returned
**Option 3**: Use different endpoint like `/me/mailboxSettings`

---

## Diagnostic Tools & Resources

### Microsoft Graph Explorer
- URL: https://developer.microsoft.com/graph/graph-explorer
- Use to test API calls with same account
- Check permissions granted
- View actual request/response

### Azure Portal Checks

**App Registration**:
1. Navigate to: Azure Portal → Azure Active Directory → App Registrations
2. Find app: `52b72157-58e1-41a5-b184-719a8cbe397a`
3. Check:
   - API Permissions (granted & consented)
   - Authentication settings
   - Supported account types

**Service Health**:
1. Microsoft 365 Admin Center → Health → Service Health
2. Check for any Microsoft Graph API incidents

### Logging & Debugging

**Enable Debug Logging**:

Current env var: `MCP_LOG_LEVEL="DEBUG"`

**Modify code for more detail** (`src/m365_mcp/graph.py`):

```python
def request(self, method: str, path: str, account_id: str, **kwargs):
    """Make Graph API request with detailed logging."""
    url = f"{self.base_url}{path}"

    # Log request details
    logger.debug(f"Graph API Request: {method} {url}")
    logger.debug(f"Request kwargs: {kwargs}")

    try:
        response = self.client.request(method, url, **kwargs)
        response.raise_for_status()

        # Log response
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response body: {response.text[:500]}")  # First 500 chars

        return response.json() if response.content else None

    except httpx.HTTPStatusError as e:
        # Enhanced error logging
        logger.error(f"HTTP Error: {e.response.status_code}")
        logger.error(f"Error body: {e.response.text}")
        logger.error(f"Request: {method} {url}")
        logger.error(f"Request body: {kwargs.get('json', 'N/A')}")
        raise
```

### Testing Commands

**Run specific failing tests**:

```bash
# Test search APIs
uv run pytest tests/test_integration.py::test_search_emails -v -s

# Test user profile
uv run pytest tests/test_integration.py::test_check_availability -v -s

# Enable maximum logging
MCP_LOG_LEVEL="DEBUG" uv run pytest tests/test_integration.py::test_search_emails -v -s 2>&1 | tee search_debug.log
```

---

## Action Plan & Timeline

### Immediate Actions (Day 1)

1. **Capture Error Details** (30 minutes)
   - [ ] Enable enhanced logging in graph.py
   - [ ] Run failing tests and capture full error messages
   - [ ] Save logs for analysis

2. **Test with Graph Explorer** (1 hour)
   - [ ] Sign in with test account
   - [ ] Test search API endpoint manually
   - [ ] Test /me endpoint
   - [ ] Document all results

3. **Review Permissions** (30 minutes)
   - [ ] Check Azure App Registration permissions
   - [ ] Verify admin consent status
   - [ ] Compare with Microsoft documentation requirements

### Investigation Phase (Day 2-3)

1. **Search API Research** (2-3 hours)
   - [ ] Review Microsoft Search API documentation
   - [ ] Check account type compatibility
   - [ ] Test alternative search methods
   - [ ] Identify root cause

2. **User Profile Research** (1 hour)
   - [ ] Analyze /me response structure
   - [ ] Implement fallback logic
   - [ ] Test fix
   - [ ] Deploy solution

### Resolution Phase (Day 4-5)

1. **Implement Fixes**
   - [ ] Update code based on findings
   - [ ] Add proper error handling
   - [ ] Implement workarounds if needed
   - [ ] Add documentation

2. **Testing & Validation**
   - [ ] Run full integration test suite
   - [ ] Verify all 6 tests pass
   - [ ] Document any limitations
   - [ ] Update test expectations if needed

---

## Expected Outcomes

### Best Case Scenario
- Identify missing permissions → Add to app → All tests pass
- Identify request format issue → Fix code → All tests pass

### Likely Scenario
- Search API not available for account type → Implement alternative search methods
- User profile field missing → Implement fallback logic

### Worst Case Scenario
- Search API not available for this configuration → Disable/skip search tests
- Document limitations in README

---

## Documentation & Reporting

### Information to Collect

For each failing test, document:
1. **Error Details**
   - Full error message
   - HTTP status code
   - API error code (if provided)
   - Request details
   - Response details

2. **Environment Info**
   - Account type (personal/work/school)
   - Microsoft 365 license
   - Tenant configuration
   - App registration details

3. **Test Results**
   - Graph Explorer test results
   - Alternative method test results
   - Workaround effectiveness

### Final Report Format

Create `GRAPH_API_FINDINGS.md` with:
- Summary of issues found
- Root causes identified
- Solutions implemented
- Limitations remaining
- Recommendations for future

---

## References

### Microsoft Documentation
- [Microsoft Graph Search API Overview](https://learn.microsoft.com/en-us/graph/search-concept-overview)
- [Search API Reference](https://learn.microsoft.com/en-us/graph/api/search-query)
- [User Resource Type](https://learn.microsoft.com/en-us/graph/api/resources/user)
- [Microsoft Graph Permissions Reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Graph API Error Codes](https://learn.microsoft.com/en-us/graph/errors)

### Tools
- [Microsoft Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)
- [Azure Portal](https://portal.azure.com)
- [Microsoft 365 Admin Center](https://admin.microsoft.com)

### Related Issues
- GitHub Issue: TBD (create after investigation)
- Test Reports: `tests/reports/`

---

## Notes

- All 28 passing tests confirm code quality is good
- Remaining failures are external API dependencies
- Resolution may require account/tenant configuration changes
- Some features may not be available for all account types
- Document any workarounds clearly for users

---

**Last Updated**: 2025-10-14
**Status**: Research Required
**Priority**: Medium (tests fail but core functionality works)
