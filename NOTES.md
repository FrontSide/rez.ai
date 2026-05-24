# Dev notes

## Pending: deploy feature-self-hosted-auth

Before merging and deploying the `feature-self-hosted-auth` branch:

- [ ] **Google Cloud Console** — add Authorised Redirect URIs for `/api/auth/callback`:
  - `http://localhost:8000/api/auth/callback` (local dev)
  - `http://192.168.178.162:8090/api/auth/callback` (homelab prod)
  - Remove the old Supabase redirect URI
- [ ] **Server `.env`** — replace old Supabase vars with:
  ```
  SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
  GOOGLE_CLIENT_ID=...
  GOOGLE_CLIENT_SECRET=...
  GOOGLE_REDIRECT_URI=http://192.168.178.162:8090/api/auth/callback
  ```

> Note: existing saved recipes in the DB are keyed to Supabase user IDs and won't carry over. One-time loss.
