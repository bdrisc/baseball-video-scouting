# Step 8: Private season-wide authentication

The public portfolio stack and URL are unchanged. `template.private.yaml` creates
a **separate** Lambda, API Gateway HTTP API, Cognito user pool, and restricted
IAM role. The private API requires a scoped Cognito access token at API Gateway
for `/`, `/docs`, `/health`, and all other application routes. Only CORS
`OPTIONS` preflight routes are anonymous. The pool is invite-only and requires
an authenticator-app MFA code. The browser uses authorization code + PKCE.

The initial private frontend runs on your laptop at `http://localhost:5173/`.
The static frontend is not hosted privately by this step. Keep this separate
from the public CloudFront frontend: a private frontend build must target only
the private API. Even if someone obtains its frontend files, the season-wide
database remains behind API Gateway authentication.

## Before deploying

1. Apply migrations 001–003 to Neon's `private-season-wide` branch as its
   **owner**. Confirm the connection endpoint is the private branch; the
   public production endpoint is different.
2. In AWS Secrets Manager (us-east-1), create a **new** secret named
   `baseball-video-scouting/private-season-wide/database`. Its JSON value
   must be `{ "DATABASE_URL": "postgresql://..." }`, using a role with the
   required table permissions on the private Neon branch. Do not reuse the
   public `baseball-video-scouting/database` secret or paste credentials into
   PowerShell commands, Git, or chat.
3. Record that new secret's ARN. Your authenticated private API can write
   playlists (`READ_ONLY_MODE=false`); grant this role only the permissions
   required for normal application queries and playlist writes.

No private AWS resources should be created until the distinct private database
secret exists and points to the correct Neon branch.

## Validate and deploy the private stack

From the repository root, with Docker Desktop running and your SSO profile
logged in:

```powershell
sam validate --template-file template.private.yaml --lint `
  --profile baseball-scouting --region us-east-1
sam build --template-file template.private.yaml `
  --build-dir .aws-sam/private-build
```

Deploy with `sam deploy --guided --template-file .aws-sam/private-build/template.yaml`
under the **new** stack name `baseball-video-scouting-private`. Choose region
`us-east-1`, IAM role creation, a unique lowercase `PrivateAuthDomainPrefix`,
the ARN of your **private** secret, and confirm the exact
`PrivateFrontendOrigin=http://localhost:5173` and
`PrivateCallbackUrl=http://localhost:5173/`. Preview the change set and verify
that it creates new resources rather than modifying
`baseball-video-scouting-portfolio`. Save the output values `PrivateApiUrl`,
`UserPoolId`, `ClientId`, `Issuer`, and `AuthDomain`.

In Cognito, create only your own user via an administrator invitation. Complete
the password change and authenticator-app setup on your first sign-in. Leave
self-registration disabled.

## Run the private browser locally

Create ignored `frontend/.env.private.local` with values from the **private**
stack outputs:

```dotenv
VITE_API_BASE_URL=https://YOUR_PRIVATE_API_ID.execute-api.us-east-1.amazonaws.com
VITE_AUTH_MODE=private
VITE_READ_ONLY_MODE=false
VITE_COGNITO_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/YOUR_PRIVATE_POOL_ID
VITE_COGNITO_CLIENT_ID=YOUR_PRIVATE_CLIENT_ID
VITE_COGNITO_AUTH_DOMAIN=https://YOUR_PRIVATE_PREFIX.auth.us-east-1.amazoncognito.com
```

These values identify endpoints and an OAuth public client; **never** put a
database URL, AWS credentials, or a Cognito client secret in a `VITE_` value.
From `frontend`:

```powershell
npm ci
npm run dev -- --mode private
```

Open **http://localhost:5173/** exactly. A sign-in screen appears before the
scouting workspace starts making API requests. After the Cognito redirect,
API calls include an access token with the custom scope
`baseball-video-scouting/access`. Browser tokens remain in session storage,
not local storage. Sign out when finished.

## Confirm access control

Before signing in, the API must reject unauthenticated calls (401):

```powershell
$privateApi = "https://YOUR_PRIVATE_API_ID.execute-api.us-east-1.amazonaws.com"
try {
  Invoke-WebRequest "$privateApi/seasons" -ErrorAction Stop
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Then sign in at `http://localhost:5173/`, select a pitcher and confirm the
browser can reach `/seasons`, `/pitchers/search`, and `/pitches`. A 401 without
a token and successful signed-in requests establish that the JWT authorizer
protects the separate API. The production portfolio URL should still display
only its original curated dataset. Do not deploy the private Vite build to the
public S3 bucket.
