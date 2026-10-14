"""What user-supplied values must look like to be written into generated HAProxy config.

Shared by the API schemas (reject at write time, with a 422) and the config
renderer (last line of defence for rows saved before a check existed), so the
two cannot drift apart.
"""

import re

# HAProxy host values used in ACL conditions: bare hostname characters only.
# The HAProxy template strips the request port before matching.
HAPROXY_HOST_PATTERN = re.compile(r"^[A-Za-z0-9._-]+\Z")


def host_error(value: str, field: str) -> str | None:
    """Why `value` cannot be written as a hostname into HAProxy config, or None."""
    if not value:
        return f"{field} must not be empty"
    if not HAPROXY_HOST_PATTERN.match(value):
        return (
            f"{field} {value!r} contains characters unsafe for HAProxy config; "
            "only hostname chars (letters, digits, dots, hyphens, underscores) "
            "are allowed"
        )
    return None
