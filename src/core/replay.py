import json
import os
from datetime import datetime, timedelta
from typing import List

from loguru import logger

from src.config import Config
from src.core.game_time import GameTime
from src.core.map import GameMap
from src.entities.character import Character
from src.entities.location import Notice
from src.core.map import place_homes_for_characters


class ReplaySimulation:
    def __init__(self, log_path: str, humanity_path: str = "data/characters.json"):
        self.game_map = GameMap()
        self.characters: List[Character] = []
        self.humanity_path = humanity_path
        self.log_path = log_path

        self.events = []
        self.start_time = None
        self.end_time = None
        self.current_time = None

        # 回放控制
        self.paused = True
        self.speed = 1.0
        self.minutes_per_tick = Config.MINUTES_PER_TICK
        self.is_replay = True

        # 加载数据
        self._load_characters()
        self._load_log()

        # 初始化状态
        if self.start_time:
            self.current_time = self.start_time
            self.game_time = GameTime()  # 占位用，随后覆盖 current_time
            self.game_time.current_time = self.start_time
            self._update_character_states()

    def _load_characters(self):
        if not os.path.exists(self.humanity_path):
            return

        try:
            with open(self.humanity_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for char_data in data:
                char = Character.from_dict(char_data)
                self.characters.append(char)
        except Exception as e:
            logger.error(f"Failed to load characters: {e}")

        # 初始化住宅
        # 这里只需确保地图上存在地点
        self._init_map_locations()

    def _init_map_locations(self):
        try:
            place_homes_for_characters(self.game_map, self.characters)
        except Exception as e:
            logger.error(f"Failed to init map locations for replay: {e}")

    def _load_log(self):
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                self.events = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load log: {e}")
            return

        # 解析时间戳
        parsed_events = []
        for event in self.events:
            ts_str = event.get("timestamp")
            try:
                # 先尝试完整格式
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    # 回退到 HH:MM（假定为默认日期 2025-01-01）
                    t = datetime.strptime(ts_str, "%H:%M")
                    ts = datetime(2025, 1, 1, t.hour, t.minute)
                except ValueError:
                    continue

            event["_dt"] = ts
            parsed_events.append(event)

        self.events = sorted(parsed_events, key=lambda x: x["_dt"])

        if self.events:
            self.start_time = self.events[0]["_dt"]
            self.end_time = self.events[-1]["_dt"] + timedelta(minutes=60)  # 添加缓冲

    def update(self):
        if not self.paused and self.current_time and self.end_time:
            self.current_time += timedelta(minutes=self.minutes_per_tick * self.speed)
            if self.current_time > self.end_time:
                self.current_time = self.end_time
                self.paused = True

            self.game_time.current_time = self.current_time
            self._update_character_states()
            self._update_notice_board()

    def toggle_pause(self):
        self.paused = not self.paused

    def change_speed(self, delta: float):
        self.speed = max(0.5, min(10.0, self.speed + delta))

    def jump_minutes(self, minutes: int):
        if not self.current_time:
            return
        if minutes > 0 and self.end_time:
            self.current_time = min(
                self.end_time, self.current_time + timedelta(minutes=minutes)
            )
        elif minutes < 0 and self.start_time:
            self.current_time = max(
                self.start_time, self.current_time + timedelta(minutes=minutes)
            )
        self.game_time.current_time = self.current_time
        self._update_character_states()
        self._update_notice_board()

    def set_time_by_progress(self, progress: float):
        self.set_time(progress)

    def set_time(self, progress: float):
        if not self.start_time or not self.end_time:
            return

        total_duration = (self.end_time - self.start_time).total_seconds()
        target_seconds = total_duration * progress
        self.current_time = self.start_time + timedelta(seconds=target_seconds)
        self.game_time.current_time = self.current_time
        self._update_character_states()
        self._update_notice_board()

    def _update_notice_board(self):
        """重建公告板状态"""
        square = self.game_map.get_location("小镇广场")
        if not square:
            return

        # 收集所有截止到当前时间的公告发布事件
        valid_notices = []

        for event in self.events:
            if event["_dt"] > self.current_time:
                break

            if event["type"] == "plan":
                details = event.get("details", {})
                action = details.get("action", "")
                target = details.get("target_location", "")

                # 检查是否是发布公告
                if "Post Notice" in action and target == "小镇广场":
                    author = details.get("character", "Unknown")
                    content = details.get("dialogue", "")
                    # 使用事件时间作为发布时间
                    created_at = event["_dt"].strftime("%Y-%m-%d %H:%M")

                    notice = Notice(
                        content=content, author=author, created_at=created_at
                    )
                    # 插入到开头（最新的在前）
                    valid_notices.insert(0, notice)

        # 仅保留最新的 5 条
        square.notices = valid_notices[:5]

    def _update_character_states(self):
        # char_name -> 最新计划事件 映射
        active_plans = {}

        # 同时查找最近的对话
        recent_dialogues = []

        for event in self.events:
            if event["_dt"] > self.current_time:
                break

            if event["type"] == "plan":
                char_name = event["details"].get("character")
                active_plans[char_name] = event
            elif event["type"] == "dialogue":
                # 检查对话是否“近期”（如 10 分钟内）
                if (self.current_time - event["_dt"]).total_seconds() < 10 * 60:
                    recent_dialogues.append(event)

        # 应用计划
        for char in self.characters:
            plan = active_plans.get(char.profile.name)
            if plan:
                # 检查计划是否仍在进行中
                start_time = plan["_dt"]
                duration = plan["details"].get("duration", 15)
                end_time = start_time + timedelta(minutes=duration)

                if self.current_time <= end_time:
                    # 正在进行中
                    target = plan["details"].get("target_location")
                    action = plan["details"].get("action")
                    emoji = plan["details"].get("emoji", "👤")

                    char.current_location = target
                    char.status = f"{action} (Replay)"
                    char.emoji = emoji

                    # 更新位置
                    loc = self.game_map.get_location(target)
                    if loc:
                        # 可在此添加更平滑的插值逻辑
                        # 当前简单地设置位置。要实现平滑回放，需要先前位置数据。
                        char.position = loc.coordinates

                        # 若要平滑移动，可把计划开始的前 10 分钟视为移动阶段
                        time_since_start = (
                            self.current_time - start_time
                        ).total_seconds()
                        if time_since_start < 60 * 10:  # 前 10 分钟视作移动
                            # 没有完整的先前位置信息，暂不处理
                            pass
                else:
                    # 计划已结束
                    char.status = "Idle"
                    char.emoji = "👤"
            else:
                char.status = "Idle"
                char.emoji = "👤"
                # 重置回家
                char.current_location = char.profile.home_location

        # 应用对话（覆盖状态）
        for diag in recent_dialogues:
            participants = diag["details"].get("participants", [])
            messages = diag["details"].get("messages", [])

            # 只显示最后一条消息或通用的“正在交谈”提示
            for char in self.characters:
                if char.profile.name in participants:
                    char.status = f"Talking... (Replay)"
                    # 尝试找到他们的具体发言
                    for msg in messages:
                        if msg["speaker"] == char.profile.name:
                            char.status = f"Said: {msg['content']}"
