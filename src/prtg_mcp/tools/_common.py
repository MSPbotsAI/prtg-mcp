from .._json import error_envelope

NO_TOKEN = error_envelope(
    "not_configured",
    "No PRTG credentials. Send the X-PRTG-Server-Url, X-PRTG-Username, and X-PRTG-Passhash headers.",
    False,
)
