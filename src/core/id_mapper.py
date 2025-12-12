"""
ID 映射器：管理规范化 ID 与中文名称之间的双向映射。
支持角色和位置的规范化 ID 系统。
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IDMapping:
    """ID 映射关系"""

    canonical_id: str  # "char_abigail" "loc_town_square"
    zh_name: str
    en_name: str


class CharacterIDMapper:
    """角色 ID 映射器"""

    PREFIX = "char"

    def __init__(self):
        self.id_to_zh: Dict[str, str] = {}  # char_abigail -> 阿比盖尔
        self.zh_to_id: Dict[str, str] = {}  # 阿比盖尔 -> char_abigail
        self.id_to_en: Dict[str, str] = {}  # char_abigail -> Abigail

    def register(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册角色 ID 映射"""
        if not canonical_id.startswith(f"{self.PREFIX}_"):
            raise ValueError(
                f"角色 ID 必须以 '{self.PREFIX}_' 开头，收到: {canonical_id}"
            )

        # 验证唯一性
        if canonical_id in self.id_to_zh:
            raise ValueError(f"角色 ID 已存在: {canonical_id}")
        if zh_name in self.zh_to_id:
            raise ValueError(f"中文名称已存在: {zh_name}")

        self.id_to_zh[canonical_id] = zh_name
        self.zh_to_id[zh_name] = canonical_id
        self.id_to_en[canonical_id] = en_name

    def get_id_from_zh(self, zh_name: str) -> Optional[str]:
        """从中文名称获取规范 ID"""
        return self.zh_to_id.get(zh_name)

    def get_zh_from_id(self, canonical_id: str) -> Optional[str]:
        """从规范 ID 获取中文名称"""
        return self.id_to_zh.get(canonical_id)

    def get_en_from_id(self, canonical_id: str) -> Optional[str]:
        """从规范 ID 获取英文名称"""
        return self.id_to_en.get(canonical_id)

    def get_display_name(self, identifier: str) -> str:
        """获取显示名称（支持 ID 或中文名称作为输入）"""
        # 如果输入是 ID
        if identifier.startswith(f"{self.PREFIX}_"):
            zh = self.get_zh_from_id(identifier)
            en = self.get_en_from_id(identifier)
            if zh and en:
                return f"{en} ({zh})"
            return identifier

        # 如果输入是中文名称
        zh_name = identifier
        char_id = self.get_id_from_zh(zh_name)
        if char_id:
            en = self.get_en_from_id(char_id)
            if en:
                return f"{en} ({zh_name})"

        return identifier

    def normalize_output(self, text: str) -> str:
        """将 LLM 输出中的 ID 转换为中文名称（用于显示）"""
        result = text
        for char_id, zh_name in self.id_to_zh.items():
            # 替换格式如 {{char_abigail}} 或 [char_abigail] 的 ID
            result = re.sub(
                rf"\{{{{[\s]*{re.escape(char_id)}[\s]*\}}}}", zh_name, result
            )
            result = re.sub(rf"\[[\s]*{re.escape(char_id)}[\s]*\]", zh_name, result)
        return result


class LocationIDMapper:
    """位置 ID 映射器"""

    PREFIX = "loc"

    def __init__(self):
        self.id_to_zh: Dict[str, str] = {}  # loc_town_square -> 小镇广场
        self.zh_to_id: Dict[str, str] = {}  # 小镇广场 -> loc_town_square
        self.id_to_en: Dict[str, str] = {}  # loc_town_square -> Town Square

    def register(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册位置 ID 映射"""
        if not canonical_id.startswith(f"{self.PREFIX}_"):
            raise ValueError(
                f"位置 ID 必须以 '{self.PREFIX}_' 开头，收到: {canonical_id}"
            )

        # 验证唯一性
        if canonical_id in self.id_to_zh:
            if self.id_to_zh[canonical_id] == zh_name:
                return
            raise ValueError(f"位置 ID 已存在: {canonical_id}")
        if zh_name in self.zh_to_id:
            if self.zh_to_id[zh_name] == canonical_id:
                return
            raise ValueError(f"中文位置名称已存在: {zh_name}")

        self.id_to_zh[canonical_id] = zh_name
        self.zh_to_id[zh_name] = canonical_id
        self.id_to_en[canonical_id] = en_name

    def get_id_from_zh(self, zh_name: str) -> Optional[str]:
        """从中文名称获取规范 ID"""
        return self.zh_to_id.get(zh_name)

    def get_zh_from_id(self, canonical_id: str) -> Optional[str]:
        """从规范 ID 获取中文名称"""
        return self.id_to_zh.get(canonical_id)

    def get_en_from_id(self, canonical_id: str) -> Optional[str]:
        """从规范 ID 获取英文名称"""
        return self.id_to_en.get(canonical_id)

    def get_display_name(self, identifier: str) -> str:
        """获取显示名称（支持 ID 或中文名称作为输入）"""
        # 如果输入是 ID
        if identifier.startswith(f"{self.PREFIX}_"):
            zh = self.get_zh_from_id(identifier)
            en = self.get_en_from_id(identifier)
            if zh and en:
                return f"{en} ({zh})"
            return identifier

        # 如果输入是中文名称
        zh_name = identifier
        loc_id = self.get_id_from_zh(zh_name)
        if loc_id:
            en = self.get_en_from_id(loc_id)
            if en:
                return f"{en} ({zh_name})"

        return identifier

    def normalize_output(self, text: str) -> str:
        """将 LLM 输出中的 ID 转换为中文名称（用于显示）"""
        result = text
        for loc_id, zh_name in self.id_to_zh.items():
            # 替换格式如 {{loc_town_square}} 或 [loc_town_square] 的 ID
            result = re.sub(
                rf"\{{{{[\s]*{re.escape(loc_id)}[\s]*\}}}}", zh_name, result
            )
            result = re.sub(rf"\[[\s]*{re.escape(loc_id)}[\s]*\]", zh_name, result)
        return result


class ActionIDMapper:
    """动作 ID 映射器"""

    PREFIX = "act"

    def __init__(self):
        self.id_to_zh: Dict[str, str] = {}  # act_move -> 移动
        self.zh_to_id: Dict[str, str] = {}  # 移动 -> act_move
        self.id_to_en: Dict[str, str] = {}  # act_move -> Move
        self.en_to_id: Dict[str, str] = {}  # Move -> act_move

    def register(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册动作 ID 映射"""
        if not canonical_id.startswith(f"{self.PREFIX}_"):
            raise ValueError(
                f"动作 ID 必须以 '{self.PREFIX}_' 开头，收到: {canonical_id}"
            )

        self.id_to_zh[canonical_id] = zh_name
        self.zh_to_id[zh_name] = canonical_id
        self.id_to_en[canonical_id] = en_name
        self.en_to_id[en_name] = canonical_id

    def get_id_from_zh(self, zh_name: str) -> Optional[str]:
        return self.zh_to_id.get(zh_name)

    def get_id_from_en(self, en_name: str) -> Optional[str]:
        return self.en_to_id.get(en_name)

    def get_zh_from_id(self, canonical_id: str) -> Optional[str]:
        return self.id_to_zh.get(canonical_id)

    def get_en_from_id(self, canonical_id: str) -> Optional[str]:
        return self.id_to_en.get(canonical_id)

    def get_display_name(self, identifier: str) -> str:
        if identifier.startswith(f"{self.PREFIX}_"):
            zh = self.get_zh_from_id(identifier)
            en = self.get_en_from_id(identifier)
            if zh and en:
                return f"{en} ({zh})"
            return identifier
        return identifier


class IDMappingManager:
    """统一管理所有 ID 映射"""

    def __init__(self):
        self.characters = CharacterIDMapper()
        self.locations = LocationIDMapper()
        self.actions = ActionIDMapper()

    def register_character(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册角色"""
        self.characters.register(canonical_id, zh_name, en_name)

    def register_location(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册位置"""
        self.locations.register(canonical_id, zh_name, en_name)

    def register_action(self, canonical_id: str, zh_name: str, en_name: str) -> None:
        """注册动作"""
        self.actions.register(canonical_id, zh_name, en_name)

    def get_char_display_name(self, identifier: str) -> str:
        """获取角色显示名称"""
        return self.characters.get_display_name(identifier)

    def get_loc_display_name(self, identifier: str) -> str:
        """获取位置显示名称"""
        return self.locations.get_display_name(identifier)

    def get_action_display_name(self, identifier: str) -> str:
        """获取动作显示名称"""
        return self.actions.get_display_name(identifier)

    def normalize_output(self, text: str) -> str:
        """规范化 LLM 输出（替换所有 ID 为中文名称）"""
        result = text
        result = self.characters.normalize_output(result)
        result = self.locations.normalize_output(result)
        # action 没有必要规范化
        return result

    def char_id_from_zh(self, zh_name: str) -> Optional[str]:
        """从中文名称获取角色 ID"""
        return self.characters.get_id_from_zh(zh_name)

    def char_zh_from_id(self, char_id: str) -> Optional[str]:
        """从 ID 获取中文名称"""
        return self.characters.get_zh_from_id(char_id)

    def loc_id_from_zh(self, zh_name: str) -> Optional[str]:
        """从中文名称获取位置 ID"""
        return self.locations.get_id_from_zh(zh_name)

    def loc_zh_from_id(self, loc_id: str) -> Optional[str]:
        """从 ID 获取中文位置名称"""
        return self.locations.get_zh_from_id(loc_id)

    def act_id_from_zh(self, zh_name: str) -> Optional[str]:
        return self.actions.get_id_from_zh(zh_name)

    def act_id_from_en(self, en_name: str) -> Optional[str]:
        return self.actions.get_id_from_en(en_name)

    def act_zh_from_id(self, act_id: str) -> Optional[str]:
        return self.actions.get_zh_from_id(act_id)


# 全局单例
_id_manager = None


def get_id_manager() -> IDMappingManager:
    """获取全局 ID 映射管理器单例"""
    global _id_manager
    if _id_manager is None:
        _id_manager = IDMappingManager()
    return _id_manager


def init_id_mappings(
    characters_data: List[dict], locations_data: dict
) -> IDMappingManager:
    """从数据初始化 ID 映射"""
    manager = get_id_manager()

    # 注册角色
    for char in characters_data:
        zh_name = char.get("name")
        en_name = char.get("english_name", zh_name)
        canonical_id = f"char_{en_name.lower().replace(' ', '_')}"
        manager.register_character(canonical_id, zh_name, en_name)

    # 注册位置
    static_locs = locations_data.get("static_locations", [])
    for loc in static_locs:
        zh_name = loc.get("name")
        en_name = loc.get("english_name", zh_name)
        canonical_id = f"loc_{en_name.lower().replace(' ', '_')}"
        manager.register_location(canonical_id, zh_name, en_name)

    return manager
