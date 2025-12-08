# Microsoft Graph Search API and User Profile Research

## Delegated vs. Application Permissions for Graph Search API

The Microsoft Graph **Search API** (`POST /search/query`) is primarily designed for **delegated permissions** with work or school accounts (Azure AD). Microsoft documentation confirms that this endpoint **does not support personal Microsoft accounts**. Using a personal account results in `400 Bad Request` errors, as the API cannot route the request for consumer accounts.

**Permission summary:**
- **Delegated (Work/School)** – Supported. Requires scopes matching searched content (e.g., `Mail.Read`, `Files.Read`, `Calendars.Read`).
- **Delegated (Personal)** – **Not supported**.
- **Application** – Limited support for specific entities (e.g., `Files.Read.All`, `Sites.Read.All` for file/site searches). Not for mail/events.

All search queries run in user context and are security-trimmed to that user’s accessible content. Application permissions are supported only for file and site searches.

## Personal Accounts vs. Work Accounts Support

The `/search/query` endpoint is **not available for personal (Outlook.com, Hotmail) accounts**. Microsoft confirmed this in official documentation and community posts:

> “Microsoft Graph Search API does not fully support searching personal OneDrive accounts using `/search/query`; it is primarily for OneDrive for Business and SharePoint.”

If tests use a personal account, all unified search calls will fail by design.

**Workarounds:**
- Use service-specific search endpoints:
  - `GET /me/drive/root/search(q='{text}')` for files.
  - `GET /me/messages?$search="keyword"` for emails.
  - `GET /me/events?$search="meeting"` for calendar events.
- These work with both personal and work accounts but only within their respective services.

## API Endpoints, Permissions, and Request Formats

### `/search/query` Request Structure

```json
{
  "requests": [
    {
      "entityTypes": ["message"],
      "query": { "queryString": "test" },
      "from": 0,
      "size": 25
    }
  ]
}
```

**Supported entity types:** `message`, `event`, `driveItem`, `site`, `listItem`, `chatMessage`, `externalItem`. (No `contact` support.)

**Required scopes:**
- `message` → `Mail.Read`
- `event` → `Calendars.Read`
- `driveItem` → `Files.Read`
- `listItem`, `site` → `Sites.Read`
- `externalItem` → `ExternalItem.Read.All`

**Common causes of 400 errors:**
- Unsupported entity type (e.g., `contact`).
- Personal account token.
- Invalid or expired token.
- Missing `Content-Type: application/json` header.
- Request exceeds `size` limit or invalid pagination.

### Alternative Endpoints

Use OData `$search` for personal or limited accounts:
- **Emails:** `GET /me/messages?$search="subject:report"`
- **Events:** `GET /me/events?$search="team"`
- **Files:** `GET /me/drive/root/search(q='budget')`

These endpoints are simpler and fully supported across account types.

## User Profile API (`/me`) – Missing `mail` Field

The `/me` endpoint often returns `mail` as null, especially for:
- Azure AD users without Exchange mailboxes.
- Guest accounts.
- Personal accounts (where `userPrincipalName` is typically the sign-in email).

### Recommended Fallback Logic

```python
me_info = graph.request("GET", "/me", account_id)
email = (
    me_info.get("mail") or
    me_info.get("userPrincipalName") or
    (me_info.get("otherMails", []) or [None])[0]
)
if not email:
    raise ValueError("Failed to get user email address")
```

**Rationale:**
- `mail` is not guaranteed.
- `userPrincipalName` is always present and reliable.
- `otherMails` may contain alternate addresses.

Adding `$select=mail,userPrincipalName` in the `/me` query can ensure retrieval, but fallback logic remains necessary.

## Summary of Root Causes

| Issue | Likely Cause | Recommended Fix |
|--------|---------------|----------------|
| 400 Bad Request (Search API) | Personal account unsupported | Use per-service search or org account |
| 400 Bad Request (Invalid entityType) | Unsupported `contact` type | Remove or replace with `$filter` on Contacts API |
| Missing `mail` field | Field not populated for account | Use fallback to `userPrincipalName` |

## References

- [Microsoft Graph Search API Overview](https://learn.microsoft.com/en-us/graph/search-concept-overview)
- [Search Query Reference](https://learn.microsoft.com/en-us/graph/api/search-query)
- [User Resource Type](https://learn.microsoft.com/en-us/graph/api/resources/user)
- [Microsoft Permissions Reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Known Issues: Search API](https://learn.microsoft.com/en-us/graph/search-known-issues)

## Conclusion

The six failing integration tests stem from external Graph API behavior:
- **Search failures (5 tests):** `/search/query` unsupported for personal accounts.
- **Profile failure (1 test):** `mail` field missing; use fallback.

Resolution requires switching to a work/school account or adopting service-specific search endpoints for personal accounts, plus adding robust fallback logic for user profile retrieval.

---

## Addendum

### How to Identify Personal vs. Work/School Microsoft Accounts

**1. Domain Pattern (Fastest Heuristic)**

* **Personal accounts**: Usually have domains like `@outlook.com`, `@hotmail.com`, `@live.com`, or other consumer aliases.
* **Work/School accounts**: Typically use custom organizational domains (e.g., `@contoso.com`, `@company.org`).

> ⚠️ Some organizations use `@outlook.com`-style vanity domains, so domain pattern alone isn't foolproof.

---

**2. Microsoft Graph `/me` Response Indicators**
Use:

```bash
GET https://graph.microsoft.com/v1.0/me
```

Key field differences:

| Field                          | Work/School                                                    | Personal                                         |
| ------------------------------ | -------------------------------------------------------------- | ------------------------------------------------ |
| `id`                           | GUID (Azure AD object ID)                                      | GUID, but in a separate MSA tenant namespace     |
| `userPrincipalName`            | org domain (e.g., [user@contoso.com](mailto:user@contoso.com)) | often same as email, but domain like outlook.com |
| `mail`                         | may be null if no Exchange license                             | typically matches `userPrincipalName`            |
| `businessPhones`               | populated                                                      | empty                                            |
| `jobTitle`, `department`, etc. | may exist                                                      | usually empty                                    |

If the `userPrincipalName` domain is `outlook.com` or `hotmail.com`, it’s a **personal Microsoft account**.

---

**3. Token Issuer Claim (`iss`) Analysis**
Inspect the JWT access token:

```bash
jwt.io
```

Check the `iss` (issuer) claim:

* **Work/School account** → `https://login.microsoftonline.com/<tenant_id>/v2.0`
* **Personal account** → `https://login.microsoftonline.com/consumers/v2.0`

If the issuer contains **`consumers`**, the token is from a **personal Microsoft account**.

---

**4. Microsoft Graph Beta `/me?$select=tenantId` (or via /organization)**

* For work/school accounts: returns a valid `tenantId` and `/organization` endpoint is accessible.
* For personal accounts: `tenantId` corresponds to the `consumers` tenant, and `/organization` returns a 404.

---

**5. Azure AD App Registration Settings (Indirect Check)**
If the app registration allows **“Accounts in any organizational directory and personal Microsoft accounts”**, both types can log in. You can infer the account type from the token issuer or the `/me` data during runtime.

---

### Summary Table

| Check                   | Work/School      | Personal               |
| ----------------------- | ---------------- | ---------------------- |
| Domain                  | Custom / Org     | outlook.com / live.com |
| `/me.userPrincipalName` | org domain       | outlook.com domain     |
| `/me.department`        | often set        | null                   |
| Token `iss` claim       | tenant_id        | consumers              |
| `/organization` API     | returns org info | fails 404              |

---

**Recommended Programmatic Check (Python Example):**

```python
profile = graph.request("GET", "/me", account_id)
issuer = decode_jwt(access_token)['iss']
if 'consumers' in issuer or profile['userPrincipalName'].endswith(('outlook.com','hotmail.com','live.com')):
    account_type = 'personal'
else:
    account_type = 'work_or_school'
```

---

**Summary:**

* The most reliable identification is via the JWT `iss` claim (`consumers` = personal, tenant ID = work/school).
* The `/me` endpoint and domain patterns can be used as quick heuristics.
* For Graph API testing, always prefer work/school accounts for endpoints like `/search/query`, as personal accounts lack support for many enterprise APIs.
