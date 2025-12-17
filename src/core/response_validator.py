import re
from typing import Dict, Optional, Any

from loguru import logger

from src.core.id_mapper import get_id_manager


class LLMResponseValidator:
    @staticmethod
    def validate_planning_response(
        response_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证和转换规划响应
        """
        manager = get_id_manager()

        # 验证必需字段
        required_fields = ["action", "target_location", "dialogue", "emoji", "duration"]
        for field in required_fields:
            if field not in response_json:
                raise ValueError(f"缺少必需字段: {field}")

        # 转换 target_location：从 ID 转换为中文名称
        target_loc_id = response_json.get("target_location", "").strip()

        # 如果输入看起来像是中文名称，直接使用
        if not target_loc_id.startswith("loc_"):
            # 假设它已经是中文名称，直接返回
            logger.debug(
                f"Target location 看起来不是 ID 格式: {target_loc_id}，假设为中文名称"
            )
            target_location_zh = target_loc_id
        else:
            # 这是一个规范 ID，转换为中文名称
            target_location_zh = manager.loc_zh_from_id(target_loc_id)
            if not target_location_zh:
                logger.warning(
                    f"无法转换位置 ID: {target_loc_id}. "
                    f"可用的位置 ID: {list(manager.locations.id_to_zh.keys())}"
                )
                # 回退：尝试使用 ID 本身作为位置名称
                target_location_zh = target_loc_id

        # 创建转换后的响应
        converted_response = {
            "action": response_json.get("action", ""),
            "target_location": target_location_zh,
            "dialogue": response_json.get("dialogue", ""),
            "emoji": response_json.get("emoji", "👤")[0],
            "duration": int(response_json.get("duration", 120)),
        }

        # 验证 action 不为空
        if not converted_response["action"].strip():
            raise ValueError("action 不能为空")

        # 验证 action 是否为有效 ID（如果是 ID 格式）
        action_input = converted_response["action"]
        if action_input.startswith("act_"):
            if not manager.act_zh_from_id(action_input):
                logger.warning(f"未知的动作 ID: {action_input}")

        return converted_response

    @staticmethod
    def validate_dialogue_response(response_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和转换对话响应
        """
        # 验证必需字段
        if "content" not in response_json:
            raise ValueError("对话响应缺少 'content' 字段")

        content = response_json.get("content", "").strip()
        if not content:
            raise ValueError("对话内容不能为空")

        # 规范化内容
        manager = get_id_manager()
        normalized_content = manager.normalize_output(content)

        return {"content": normalized_content}

    @staticmethod
    def extract_and_convert_location_id(location_id: str) -> Optional[str]:
        """
        提取并转换位置 ID 为中文名称
        """
        manager = get_id_manager()

        # 清理输入
        location_id = location_id.strip()

        # 如果已经是中文名称
        if not location_id.startswith("loc_"):
            return location_id

        # 转换 ID 为中文名称
        zh_name = manager.loc_zh_from_id(location_id)
        return zh_name

    @staticmethod
    def extract_character_name_from_reference(char_reference: str) -> Optional[str]:
        """
        从字符引用提取角色名称
        """
        manager = get_id_manager()
        char_reference = char_reference.strip()

        # 如果是 ID 格式
        if char_reference.startswith("char_"):
            zh_name = manager.char_zh_from_id(char_reference)
            return zh_name

        # 如果是中文名称（检查是否在映射中）
        char_id = manager.char_id_from_zh(char_reference)
        if char_id:
            return char_reference  # 已经是中文名称

        # 如果是英文名称，尝试转换
        # 构造可能的 ID
        possible_id = f"char_{char_reference.lower().replace(' ', '_')}"
        zh_name = manager.char_zh_from_id(possible_id)
        if zh_name:
            return zh_name

        # 无法识别
        logger.warning(f"无法识别角色引用: {char_reference}")
        return None


class ContextBuilder:
    """构建用于 LLM 提示词的上下文信息（使用 ID）"""

    @staticmethod
    def build_locations_context(locations_dict: Dict[str, Any]) -> str:
        """
        构建位置列表上下文（使用规范 ID）

        Args:
            locations_dict: 位置对象字典 {位置名称: Location 对象}

        Returns:
            格式化的位置上下文字符串
        """
        manager = get_id_manager()
        location_descriptions = []

        for zh_name, loc in locations_dict.items():
            # 获取规范 ID
            loc_id = manager.loc_id_from_zh(zh_name)
            if not loc_id:
                logger.warning(f"找不到位置 '{zh_name}' 的规范 ID")
                loc_id = f"loc_{zh_name}"

            # 获取英文名称
            en_name = manager.locations.get_en_from_id(loc_id) or zh_name

            # 创建位置描述
            description = f"- {loc_id}: {en_name} ({zh_name}) - {loc.description}"
            location_descriptions.append(description)

        return "\n".join(location_descriptions)

    @staticmethod
    def build_characters_context(
        characters_list: list,
        exclude_char: Any = None,
    ) -> str:
        """
        构建角色位置上下文
        """
        manager = get_id_manager()
        char_contexts = []

        for char in characters_list:
            # 如果需要排除该角色
            if exclude_char and char.profile.name == exclude_char.profile.name:
                continue

            # 获取角色名称
            char_name = char.profile.name
            en_name = char.profile.english_name or char_name

            # 获取角色当前位置
            current_loc_zh = char.current_location
            loc_id = manager.loc_id_from_zh(current_loc_zh)

            if loc_id:
                loc_display = f"{loc_id} ({current_loc_zh})"
            else:
                loc_display = current_loc_zh

            # 获取状态概要
            status_summary = (
                char.status.split("(")[0].strip() if "(" in char.status else char.status
            )

            # 创建角色上下文
            context = f"{en_name} ({char_name}): {loc_display} [{status_summary}]"
            char_contexts.append(context)

        return ", ".join(char_contexts)


class ResponseConverter:
    """将 LLM 响应从 ID 转换回内部格式"""

    @staticmethod
    def convert_planning_response_to_internal(
        validated_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        验证后的响应已经包含中文位置名称，可以直接使用
        """
        return validated_response

    @staticmethod
    def normalize_character_references(text: str) -> str:
        """
        规范化文本中的角色引用
        """
        manager = get_id_manager()
        result = text

        # 规范化 ID 引用
        for char_id, zh_name in manager.characters.id_to_zh.items():
            result = re.sub(
                rf"\b{re.escape(char_id)}\b", zh_name, result, flags=re.IGNORECASE
            )

        return result
