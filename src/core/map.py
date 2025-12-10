from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel
import json
import os


class LocationType(Enum):
    SQUARE = "Square"
    SALOON = "Saloon"
    HOME = "Home"
    LIBRARY = "Library"


class Notice(BaseModel):
    content: str
    author: str
    created_at: str


class Location(BaseModel):
    name: str
    type: LocationType
    description: str
    connected_locations: List[str] = []
    coordinates: tuple[int, int] = (0, 0)  # 渲染用
    notices: List[Notice] = []


class GameMap:
    def __init__(self):
        self.locations: Dict[str, Location] = {}
        self._init_map()

    def _init_map(self):
        try:
            with open("data/locations.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            for loc_data in data.get("static_locations", []):
                # 将类型字符串映射为枚举
                type_str = loc_data["type"].upper()
                loc_type = (
                    LocationType[type_str]
                    if type_str in LocationType.__members__
                    else LocationType.SQUARE
                )

                self.add_location(
                    Location(
                        name=loc_data["name"],
                        type=loc_type,
                        description=loc_data["description"],
                        coordinates=tuple(loc_data["coordinates"]),
                    )
                )

            # 处理地点之间的连接关系
            for loc_data in data.get("static_locations", []):
                name = loc_data["name"]
                for target in loc_data.get("connected_to", []):
                    self.connect_locations(name, target)

        except Exception as e:
            print(f"Error loading locations.json: {e}")
            # 回退：当文件缺失或出错时使用默认地点
            self.add_location(
                Location(
                    name="小镇广场",
                    type=LocationType.SQUARE,
                    description="The center of town.",
                    coordinates=(400, 300),
                )
            )

    def add_location(self, location: Location):
        self.locations[location.name] = location

    def connect_locations(self, loc1_name: str, loc2_name: str):
        if loc1_name in self.locations and loc2_name in self.locations:
            if loc2_name not in self.locations[loc1_name].connected_locations:
                self.locations[loc1_name].connected_locations.append(loc2_name)
            if loc1_name not in self.locations[loc2_name].connected_locations:
                self.locations[loc2_name].connected_locations.append(loc1_name)

    def get_location(self, name: str) -> Optional[Location]:
        return self.locations.get(name)

    def add_home(self, owner_name: str, coordinates: tuple[int, int]):
        home_name = f"{owner_name}的家"
        self.add_location(
            Location(
                name=home_name,
                type=LocationType.HOME,
                description=f"{owner_name}的家。包括客厅、卧室和厨房。",
                coordinates=coordinates,
            )
        )
        self.connect_locations("小镇广场", home_name)
        return home_name
