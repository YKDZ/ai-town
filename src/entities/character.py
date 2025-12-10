from pydantic import BaseModel, Field
from typing import Optional, List
import os
from loguru import logger


class CharacterProfile(BaseModel):
    name: str
    age: str
    occupation: str
    personality: str
    features: str
    quote: str
    relationships: str
    residence: str
    home_location: str
    icon: str = "👤"
    mission: Optional[str] = None
    llm_config: Optional[dict] = (
        None  # { "api_key": "...", "base_url": "...", "model": "..." }
    )


class Character:
    def __init__(self, profile: CharacterProfile):
        self.profile = profile
        self.current_location = profile.home_location
        self.status = "空闲"
        self.emoji = "👤"
        self.memory: List[str] = []
        self.current_plan: str = ""
        # 结束时间的 datetime 对象
        self.busy_until: Optional[object] = None
        self.is_thinking: bool = False
        self.llm_client = None
        self.last_optimized_date = None

    def optimize_memory(self, llm_client, current_date_str):
        if not self.memory:
            return

        # 记忆太短则不优化，否则会导致行为降级
        if len(self.memory) < 3:
            return

        from src.ai.prompts import (
            MEMORY_OPTIMIZATION_SYSTEM_PROMPT,
            MEMORY_OPTIMIZATION_USER_PROMPT,
        )

        memories_text = "\n".join(self.memory)

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
            # 添加时间以维护记忆连续性
            self.memory = [f"[{current_date_str} Summary] {summary}"]
            self.last_optimized_date = current_date_str

            logger.info(f"Memory optimized for {self.profile.name}. Summary: {summary}")
        except Exception as e:
            logger.error(f"Failed to optimize memory for {self.profile.name}: {e}")

    def move_to(self, location_name: str):
        self.current_location = location_name
        self.status = f"正在前往 {location_name}"

    def say(self, message: str):
        self.status = f"正在说: {message}"

    def is_sleeping(self) -> bool:
        s = self.status
        return "Sleeping" in s or "Sleep" in s or "睡觉" in s

    def is_talking(self) -> bool:
        s = self.status
        return "Talking" in s or "Said" in s or "正在与" in s or "对" in s

    def is_working(self) -> bool:
        s = self.status
        return "Work" in s or "工作" in s

    def is_eating(self) -> bool:
        s = self.status
        return "Eat" in s or "Breakfast" in s or "吃饭" in s

    def is_thinking_status(self) -> bool:
        s = self.status
        return "Thinking" in s or "思考中" in s

    def add_memory(self, memory: str):
        self.memory.append(memory)

    @staticmethod
    def from_dict(data: dict) -> "Character":
        residence = data.get("residence", f"{data.get('name', 'Unknown')}的家")
        return Character(
            CharacterProfile(
                name=data.get("name", "Unknown"),
                age=data.get("age", "Unknown"),
                occupation=data.get("occupation", "Unknown"),
                personality=data.get("personality", "Unknown"),
                features=data.get("features", "Unknown"),
                quote=data.get("quote", "Unknown"),
                relationships=data.get("relationships", "Unknown"),
                residence=residence,
                home_location=data.get("home_location", residence),
                icon=data.get("icon", "👤"),
                mission=data.get("mission"),
                llm_config=data.get("llm_config"),
            )
        )
