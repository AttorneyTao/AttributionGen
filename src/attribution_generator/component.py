from dataclasses import dataclass
from typing import Optional

@dataclass
class Component:
    name: str
    copyright: str
    license: str
    version: Optional[str] = None
    others_url: Optional[str] = None
    modified: bool = False
    modified_url: Optional[str] = None