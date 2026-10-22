"""Versions this backend expects the rest of the stack to agree with.

`EXPECTED_CONFIG_VERSION` is the stamp every shipped `haproxy.cfg` /
`coraza.cfg` carries; bump it together with those files (see
`configs/haproxy/coraza.cfg`) when the contract they implement changes. The
backend refuses to report healthy for a bind-mounted seed config that does not
carry the expected stamp (issue #312).

`CRS_VERSION` must match the `configs/coraza/crs` submodule; bump both
together, because the generated CRS metadata is derived from it and the
submodule supplies the actual rules (issue #316).
"""

from __future__ import annotations

EXPECTED_CONFIG_VERSION = 1

CRS_VERSION = "4.25.0"
