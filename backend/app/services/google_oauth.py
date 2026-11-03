"""Google OAuth 2.0 / OpenID Connect sign-in (authorization-code flow).

1. ``authorization_url`` sends the browser to Google with a random ``state`` and ``nonce``.
2. Google redirects back with a one-time ``code``.
3. ``exchange_code`` swaps the code for tokens (server-to-server, using the client secret)
   and verifies the ID token: Google's signature, audience (our client id), issuer, expiry
   and the nonce. Only then is the identity trusted.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import Settings
from app.core.errors import AppError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str


class GoogleOAuth:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def authorization_url(self, state: str, nonce: str) -> str:
        params = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code: str, nonce: str) -> GoogleIdentity:
        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": self.settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise AppError("GOOGLE_UNREACHABLE", "Could not reach Google to finish signing in.", 502) from exc
        if response.status_code != 200 or "id_token" not in response.json():
            raise AppError("GOOGLE_CODE_REJECTED", "Google rejected the sign-in. Please try again.", 401)

        try:
            claims = id_token.verify_oauth2_token(
                response.json()["id_token"], google_requests.Request(), self.settings.google_client_id
            )
        except ValueError as exc:  # bad signature, wrong audience/issuer, expired
            raise AppError("INVALID_ID_TOKEN", "Google's sign-in token could not be verified.", 401) from exc

        if claims.get("nonce") != nonce:
            raise AppError("INVALID_ID_TOKEN", "Sign-in token does not match this sign-in attempt.", 401)

        return GoogleIdentity(
            sub=str(claims["sub"]),
            email=str(claims.get("email", "")),
            email_verified=bool(claims.get("email_verified", False)),
            name=str(claims.get("name") or claims.get("email", "")),
        )
