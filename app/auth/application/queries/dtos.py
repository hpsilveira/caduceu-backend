from dataclasses import dataclass

@dataclass(frozen=True)
class SectorDTO:
    code: str
    name: str