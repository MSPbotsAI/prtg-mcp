import contextvars
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import PRTGClient
from .config import Settings

# Per-request credential isolation via contextvars.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent SSE connections are isolated.
_gateway_creds_var: contextvars.ContextVar[tuple[str, str, str] | None] = contextvars.ContextVar(
    "prtg_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> PRTGClient | None:
    """Resolve the active PRTGClient for the current request context."""
    creds = _gateway_creds_var.get()
    if not creds:
        return None
    server_url, username, passhash = creds
    return PRTGClient(server_url, username, passhash)


class GatewayTokenMiddleware:
    """ASGI middleware.

    Reads X-PRTG-Server-Url, X-PRTG-Username, and X-PRTG-Passhash (all
    required) from request headers and stores them in the contextvar.
    Returns 401 if any is missing on /mcp requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        server_url = request.headers.get("x-prtg-server-url")
        username = request.headers.get("x-prtg-username")
        passhash = request.headers.get("x-prtg-passhash")
        if not server_url or not username or not passhash:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": (
                        "This server requires the X-PRTG-Server-Url, "
                        "X-PRTG-Username, and X-PRTG-Passhash headers"
                    ),
                    "required_headers": ["X-PRTG-Server-Url", "X-PRTG-Username", "X-PRTG-Passhash"],
                    "optional_headers": [],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set((server_url, username, passhash))
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all PRTG tools."""
    # DNS-rebinding protection is a browser-oriented safeguard that rejects
    # non-localhost Host headers with 421. Disable it so the server works
    # correctly behind a reverse proxy or docker network.
    mcp = FastMCP(
        name="prtg-mcp",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    client_factory: Callable[[], PRTGClient | None] = lambda: get_client_from_context(settings)

    from .tools import resources

    resources.register(mcp, client_factory)

    return mcp
