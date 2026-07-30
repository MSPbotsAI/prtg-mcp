import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import PRTGClient, PRTGError
from ._common import NO_TOKEN

SENSOR_COLUMNS = (
    "objid,type,name,tags,active,status,lastvalue,sensor,downtime,downtimetime,"
    "downtimesince,uptime,uptimetime,uptimesince,knowntime,device,lastcheck"
)
DEVICE_COLUMNS = "objid,probe,group,device,type,name,tags,active,grpdev,notifiesx,intervalx,status,priority"


def register(mcp: FastMCP, client_factory: Callable[[], PRTGClient | None]) -> None:

    @mcp.tool()
    async def prtg_get_sensors(count: int = 500) -> str:
        """List all sensors and their current status/values across the
        monitored infrastructure.

        API: GET /api/table.json?content=sensors

        No required parameters.

        Args:
            count: Optional. Maximum number of sensors to return. Default 500.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/api/table.json",
                {"content": "sensors", "columns": SENSOR_COLUMNS, "count": count},
            )
            return json.dumps(result, indent=2)
        except PRTGError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def prtg_get_devices(count: int = 500) -> str:
        """List all monitored devices and their status/probe/group placement.

        API: GET /api/table.json?content=devices

        No required parameters.

        Args:
            count: Optional. Maximum number of devices to return. Default 500.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.call(
                "/api/table.json",
                {"content": "devices", "columns": DEVICE_COLUMNS, "count": count},
            )
            return json.dumps(result, indent=2)
        except PRTGError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def prtg_get_sensor_historic_data(
        sensor_id: str, start_date: str, end_date: str, avg: int = 3600
    ) -> str:
        """Get historic monitoring data for a single sensor over a date range.

        API: GET /api/historicdata.json

        Args:
            sensor_id: Required. The sensor's object ID (get one from
                prtg_get_sensors).
            start_date: Required. Range start, "YYYY-MM-DD-HH-MM-SS".
            end_date: Required. Range end, "YYYY-MM-DD-HH-MM-SS".
            avg: Optional. Averaging interval in seconds (0 = raw data).
                Default 3600 (hourly), matching MSPbots' own usage.
        """
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
            return json.dumps(result, indent=2)
        except PRTGError as e:
            return f"Error: {e}"
