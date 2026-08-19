from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import PRTGClient, PRTGError
from ._common import NO_TOKEN

SENSOR_COLUMNS = (
    "objid,type,name,tags,active,status,lastvalue,sensor,downtime,downtimetime,"
    "downtimesince,uptime,uptimetime,uptimesince,knowntime,device,lastcheck"
)
DEVICE_COLUMNS = "objid,probe,group,device,type,name,tags,active,grpdev,notifiesx,intervalx,status,priority"

# PRTG's table.json `count` param has no documented hard vendor maximum, so
# this falls back to the SOP's own ceiling: default <=50, hard cap <=200.
_DEFAULT_COUNT = 50
_MAX_COUNT = 200


def _clamp_count(count: int) -> int:
    return max(1, min(count, _MAX_COUNT))


def register(mcp: FastMCP, client_factory: Callable[[], PRTGClient | None]) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def prtg_get_sensors(
        count: Annotated[
            int, Field(description="Max sensors to return. Default 50, hard cap 200.")
        ] = _DEFAULT_COUNT,
    ) -> str:
        """List all sensors and their current status/value across the monitored infrastructure."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/api/table.json",
                {"content": "sensors", "columns": SENSOR_COLUMNS, "count": _clamp_count(count)},
            )
            return dump_json_capped(result)
        except PRTGError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def prtg_get_devices(
        count: Annotated[
            int, Field(description="Max devices to return. Default 50, hard cap 200.")
        ] = _DEFAULT_COUNT,
    ) -> str:
        """List all monitored devices and their status, probe, and group placement."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/api/table.json",
                {"content": "devices", "columns": DEVICE_COLUMNS, "count": _clamp_count(count)},
            )
            return dump_json_capped(result)
        except PRTGError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
    async def prtg_get_sensor_historic_data(
        sensor_id: Annotated[
            str, Field(description="Sensor's object ID, from prtg_get_sensors.")
        ],
        start_date: Annotated[
            str, Field(description="Range start, format YYYY-MM-DD-HH-MM-SS.")
        ],
        end_date: Annotated[
            str, Field(description="Range end, format YYYY-MM-DD-HH-MM-SS.")
        ],
        avg: Annotated[
            int,
            Field(description="Averaging interval in seconds; 0 for raw data. Default 3600 (hourly)."),
        ] = 3600,
    ) -> str:
        """Get historic monitoring data for one sensor over a date range."""
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/api/historicdata.json",
                {
                    "id": sensor_id,
                    "sdate": start_date,
                    "edate": end_date,
                    "avg": avg,
                    "usecaption": 1,
                },
            )
            return dump_json_capped(result)
        except PRTGError as e:
            return e.to_envelope()
