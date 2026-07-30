import httpx


class PRTGError(Exception):
    def __init__(self, message: str):
        super().__init__(f"PRTG API error: {message}")


class PRTGClient:
    """Async httpx client wrapping the PRTG core server's native HTTP API.

    Unlike most integrations in this program, PRTG has no separate login
    or token exchange: the username and a "passhash" (generated in PRTG's
    UI under My Account -> API Key, not the literal account password) are
    sent as plain query parameters on every single call. There is
    therefore nothing to cache — each call is already fully self-contained
    and stateless.
    """

    def __init__(self, server_url: str, username: str, passhash: str):
        self._server_url = server_url.rstrip("/")
        self._username = username
        self._passhash = passhash

    def _clean(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def call(self, path: str, params: dict) -> dict:
        query = {"username": self._username, "passhash": self._passhash, **self._clean(params)}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(f"https://{self._server_url}{path}", params=query)
            except httpx.RequestError as e:
                raise PRTGError(f"{e or type(e).__name__} (path={path})") from e
            if resp.status_code >= 400:
                raise PRTGError(f"HTTP {resp.status_code} calling {path}: {resp.text}")
            return resp.json()
