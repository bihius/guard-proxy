"""What user-supplied values must look like to be written into generated SecLang.

Shared by the API schemas (reject at write time, with a 422) and the config
renderer (last line of defence for rows saved before a check existed), so the
two cannot drift apart.
"""

import re

# SecRule variable lists, e.g. "ARGS|REQUEST_HEADERS:User-Agent".
VARIABLES_PATTERN = re.compile(r"^[A-Za-z0-9_.:|@-]+$")


def quoted_value_error(value: str) -> str | None:
    """Why `value` cannot be written inside a double-quoted SecLang argument.

    The renderer escapes only `"` (as `\\"`) and leaves backslashes alone,
    because Coraza unescapes nothing else: a doubled backslash reaches the
    operator as two, which breaks regexes such as `^/a\\.b$`. With that
    encoding two inputs have no valid form. A trailing backslash would escape
    the closing quote, and a backslash before a quote becomes `\\\\"`, which
    Coraza reads as an escaped backslash followed by an unescaped quote.
    """
    if not value:
        return "must not be empty"
    if "\r" in value or "\n" in value:
        return "must not contain line breaks"
    if value.endswith("\\"):
        return "must not end with a backslash"
    if '\\"' in value:
        return 'must not contain a backslash followed by a quote (write " alone)'
    return None
