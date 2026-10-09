from typing import TypedDict
from datetime import datetime

# =========================================================================
# AUTH TOKEN CLAIMS
# =========================================================================
class TokenClaims(TypedDict):
    sub: str
    full_name: str
    role: str
    sector_code: str
    must_change_password: bool
    exp: datetime
