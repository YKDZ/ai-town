from pydantic import BaseModel, Field
from typing import Optional, List
import os
from loguru import logger


class CharacterProfile(BaseModel):
    name: str
    english_name: Optional[str] = None
    age: str
    occupation: str
    personality: str
    features: str
    relationships: str
    residence: str
    english_residence: Optional[str] = None
    home_location: str
    english_home_location: Optional[str] = None
    icon: str = "👤"
    mission: Optional[str] = None
    llm_config: Optional[dict] = (
        None  # { "api_key": "...", "base_url": "...", "model": "..." }
    )


class Character:
    def __init__(self, profile: CharacterProfile):
        self.profile = profile
        self.current_location = profile.home_location
        self.current_location_id = None  # 规范化位置 ID（loc_*），运行时维护
        self.status = "空闲"
        self.emoji = "👤"
        self.memory: List[str] = []
        self.current_plan: str = ""
        self.last_action_id: Optional[str] = None  # 规范化动作 ID（act_*）
        # 结束时间的 datetime 对象
        self.busy_until: Optional[object] = None
        self.is_thinking: bool = False
        self.llm_client = None
        self.last_optimized_date = None

    def optimize_memory(self, llm_client, current_date_str):
        if not self.memory:
            return

        # 识别现有的总结和新的日常记忆
        # 假设总结的格式包含 "Summary]"
        existing_summaries = [m for m in self.memory if "Summary]" in m]
        new_memories = [m for m in self.memory if "Summary]" not in m]

        # 如果新的记忆太少，则不进行优化
        if len(new_memories) < 3:
            return

        from src.ai.prompts import (
            MEMORY_OPTIMIZATION_SYSTEM_PROMPT,
            MEMORY_OPTIMIZATION_USER_PROMPT,
        )

        memories_text = "\n".join(new_memories)

        system_prompt = MEMORY_OPTIMIZATION_SYSTEM_PROMPT.format(name=self.profile.name)
        user_prompt = MEMORY_OPTIMIZATION_USER_PROMPT.format(
            date=current_date_str, memories=memories_text
        )

        try:
            client = self.llm_client or llm_client
            if not client:
                return

            summary = client.get_completion(user_prompt, system_prompt)

            # 应用优化后的记忆
            # 保留旧的总结，追加新的总结
            self.memory = existing_summaries + [f"[{current_date_str} Summary] {summary}"]
            self.last_optimized_date = current_date_str

            logger.info(f"Memory optimized for {self.profile.name}. Summary: {summary}")
        except Exception as e:
            logger.error(f"Failed to optimize memory for {self.profile.name}: {e}")

    def move_to(self, location_name: str):
        self.current_location = location_name
        # 更新规范 ID
        try:
            from src.core.id_mapper import get_id_manager

            loc_id = get_id_manager().loc_id_from_zh(location_name)
            self.current_location_id = loc_id or self.current_location_id
        except Exception:
            # 兜底：即使映射失败也不影响继续运行
            pass

        self.status = f"正在前往 {location_name}"

    def say(self, message: str):
        self.status = f"正在说: {message}"

    def is_sleeping(self) -> bool:
        if self.last_action_id == "act_sleep":
            return True
        s = self.status.lower()
        return "sleeping" in s or "sleep" in s or "睡觉" in s or "bed" in s

    def is_talking(self) -> bool:
        if self.last_action_id == "act_chat":
            return True
        s = self.status.lower()
        return (
            "talking" in s
            or "said" in s
            or "正在说" in s
            or "正在与" in s
            or "对" in s
            or "回复" in s
        )

    def is_working(self) -> bool:
        if self.last_action_id == "act_work":
            return True
        s = self.status.lower()
        return "working" in s or "work" in s or "工作" in s

    def is_eating(self) -> bool:
        if self.last_action_id == "act_eat":
            return True
        s = self.status.lower()
        return "eating" in s or "eat" in s or "breakfast" in s or "吃饭" in s

    def is_thinking_status(self) -> bool:
        s = self.status.lower()
        return "think" in s or "thinking" in s or "思考中" in s

    def add_memory(self, memory: str):
        self.memory.append(memory)

    @staticmethod
    def from_dict(data: dict) -> "Character":
        residence = data.get("residence", f"{data.get('name', 'Unknown')}的家")
        english_residence = data.get("english_residence")
        return Character(
            CharacterProfile(
                name=data.get("name", "Unknown"),
                english_name=data.get("english_name"),
                age=data.get("age", "Unknown"),
                occupation=data.get("occupation", "Unknown"),
                personality=data.get("personality", "Unknown"),
                features=data.get("features", "Unknown"),
                relationships=data.get("relationships", "Unknown"),
                residence=residence,
                english_residence=english_residence,
                home_location=data.get("home_location", residence),
                english_home_location=data.get(
                    "english_home_location", english_residence
                ),
                icon=data.get("icon", "👤"),
                mission=data.get("mission"),
                llm_config=data.get("llm_config"),
            )
        )
