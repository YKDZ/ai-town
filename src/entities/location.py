from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Notice(BaseModel):
    content: str
    author: str
    created_at: str


class LocationType(Enum):
    SQUARE = "Square"
    SALOON = "Saloon"
    HOME = "Home"
    LIBRARY = "Library"


class Location(BaseModel):
    name: str
    english_name: Optional[str] = None
    type: LocationType
    description: str
    connected_locations: List[str] = []
    coordinates: tuple[int, int] = (0, 0)  # 渲染用
    notices: List[Notice] = []
