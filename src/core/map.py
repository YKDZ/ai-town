import json
import math
from typing import Dict, Optional, List

from src.entities.character import Character
from src.entities.location import Location, LocationType

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
                        english_name=loc_data.get("english_name"),
                        type=loc_type,
                        description=loc_data["description"],
                        coordinates=tuple(loc_data["coordinates"]), # type: ignore[arg-type]
                    )
                )

            # 处理地点之间的连接关系
            for loc_data in data.get("static_locations", []):
                name = loc_data["name"]
                for target in loc_data.get("connected_to", []):
                    self.connect_locations(name, target)

        except Exception as e:
            print(f"Error loading locations.json: {e}")
            # 当文件缺失或出错时使用默认地点
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


def place_homes_for_characters(game_map: GameMap, characters: List[Character]):
    """将角色按其 residence 在地图上生成住宅并连到小镇广场，同时初始化角色位置
    """

    # 分组：residence -> [characters]
    residences: Dict[str, List] = {}
    for char in characters:
        res_name = getattr(char.profile, "residence", None) or getattr(
            char.profile, "home_location", ""
        )
        if res_name not in residences:
            residences[res_name] = []
        residences[res_name].append(char)

    # 载入住宅描述配置
    home_desc_config = []
    try:
        with open("data/locations.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            home_desc_config = data.get("home_descriptions", [])
    except Exception:
        # 配置缺失时静默回退
        pass

    # 环形布局参数
    center_x, center_y, radius = 400, 300, 250

    # 需要创建住宅的 residence 名称
    homes_to_place = [r for r in residences.keys() if r != "酒馆"]
    num_homes = len(homes_to_place)
    angle_step = 2 * math.pi / num_homes if num_homes > 0 else 0

    for i, home_name in enumerate(homes_to_place):
        angle = i * angle_step
        x = int(center_x + radius * math.cos(angle))
        y = int(center_y + radius * math.sin(angle))

        # 匹配住宅描述
        description = f"{home_name}."
        found_match = False
        for config in home_desc_config:
            keywords = config.get("keywords", [])
            if "default" in keywords:
                continue
            for kw in keywords:
                if kw in home_name:
                    description = config.get("description", "{name}.").format(
                        name=home_name
                    )
                    found_match = True
                    break
            if found_match:
                break
        if not found_match:
            for config in home_desc_config:
                if "default" in config.get("keywords", []):
                    description = config.get("description", "{name}.").format(
                        name=home_name
                    )
                    break

        # 从该住宅的第一位居民读取 english_home_location
        english_home_name = None
        if residences.get(home_name):
            english_home_name = residences[home_name][0].profile.english_home_location

        # 加入地图并连到广场
        loc = Location(
            name=home_name,
            english_name=english_home_name,
            type=LocationType.HOME,
            description=description,
            coordinates=(x, y),
        )
        game_map.add_location(loc)
        game_map.connect_locations(home_name, "小镇广场")

        # 初始化该住宅居民的家与当前位置
        for char in residences[home_name]:
            char.profile.home_location = home_name
            char.current_location = home_name
            char.position = (x, y)

    if "酒馆" in residences:
        saloon = game_map.get_location("酒馆")
        if saloon:
            for char in residences["酒馆"]:
                char.profile.home_location = "酒馆"
                char.current_location = "酒馆"
                char.position = saloon.coordinates
