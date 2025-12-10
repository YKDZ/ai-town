import os
import json
import math
import random
import threading
from typing import List
from loguru import logger
from datetime import timedelta

from src.core.game_time import GameTime
from src.config import Config
from src.core.map import GameMap, LocationType, Location, Notice
from src.core.logger import SimulationLogger, sim_time_var
from src.entities.character import Character
from src.ai.llm_client import LLMClient
from src.ai.prompts import (
    PLANNING_SYSTEM_PROMPT,
    PLANNING_USER_PROMPT,
    DIALOGUE_SYSTEM_PROMPT,
    DIALOGUE_USER_PROMPT,
)


class Simulation:
    def __init__(
        self,
        humanity_path: str = "data/characters.json",
        duration_days: int = Config.SIMULATION_DURATION_DAYS,
    ):
        # 加载配置
        config_path = "data/config.json"
        start_year = 2025
        start_month = 1
        start_day = 1
        start_hour = 6

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    sim_config = config_data.get("simulation", {})
                    start_year = sim_config.get("start_year", 2025)
                    start_month = sim_config.get("start_month", 1)
                    start_day = sim_config.get("start_day", 1)
                    start_hour = sim_config.get("start_hour", 6)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

        self.game_time = GameTime(start_year, start_month, start_day, start_hour)
        sim_time_var.set(self.game_time.get_display_string())
        self.game_map = GameMap()
        self.characters: List[Character] = []
        self.llm_client = LLMClient()

        # 启动前检查 LLM 可用性
        try:
            self.llm_client.check_connection()
        except Exception as e:
            logger.critical(f"LLM Check Failed: {e}")
            raise e

        self.humanity_path = humanity_path
        self.duration_days = duration_days
        self.event_day = duration_days
        
        # 计算结束时间
        self.end_time = self.game_time.current_time + timedelta(days=duration_days)
        
        self.interaction_cooldowns = {}
        self.logger = SimulationLogger()

        self._load_characters()
        self._init_homes()

    def _load_characters(self):
        if not os.path.exists(self.humanity_path):
            logger.warning(f"Character data file {self.humanity_path} does not exist.")
            return

        try:
            with open(self.humanity_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for char_data in data:
                try:
                    char = Character.from_dict(char_data)

                    # 如果配置了，为居民初始化专用的 LLM 客户端
                    if char.profile.llm_config:
                        try:
                            logger.info(
                                f"Initializing custom LLM for {char.profile.name}..."
                            )
                            char.llm_client = LLMClient(
                                api_key=char.profile.llm_config.get("api_key"),
                                base_url=char.profile.llm_config.get("base_url"),
                                model=char.profile.llm_config.get("model"),
                                temperature=char.profile.llm_config.get("temperature"),
                            )
                            char.llm_client.check_connection()
                            logger.info(f"Custom LLM for {char.profile.name} ready.")
                        except Exception as e:
                            logger.error(
                                f"Failed to init custom LLM for {char.profile.name}: {e}. Falling back to default."
                            )
                            char.llm_client = None

                    self.characters.append(char)
                    logger.info(f"Loaded character: {char.profile.name}")
                except Exception as e:
                    logger.error(f"Failed to load character data: {e}")
        except Exception as e:
            logger.error(f"Failed to load characters from {self.humanity_path}: {e}")

    def _init_homes(self):
        # 将住宅按环形布局放置在小镇广场周围
        center_x = 400
        center_y = 300
        radius = 250

        # 按住所分组居民
        residences = {}

        for char in self.characters:
            # 处理配置中的通用任务（如果有）
            if char.profile.mission:
                try:
                    # 计算目标日期
                    target_date = self.game_time.current_time + timedelta(
                        days=self.duration_days
                    )
                    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    wd = weekdays[target_date.weekday()]
                    target_date_str = f"{target_date.strftime('%Y年%m月%d日')} {wd}"

                    mission_text = char.profile.mission.format(
                        days=self.duration_days, target_date=target_date_str
                    )
                    char.add_memory(mission_text)
                    logger.info(
                        f"Initialized mission for {char.profile.name} from profile: {mission_text}"
                    )
                except Exception as e:
                    logger.error(f"Failed to load mission for {char.profile.name}: {e}")

            res_name = char.profile.residence
            # 按住所分组居民
            if res_name not in residences:
                residences[res_name] = []
            residences[res_name].append(char)

        target_date = self.game_time.current_time + timedelta(days=self.duration_days)
        # 酒馆特殊处理
        homes_to_place = [r for r in residences.keys() if r != "酒馆"]
        num_homes = len(homes_to_place)

        angle_step = 2 * math.pi / num_homes if num_homes > 0 else 0

        # 加载住宅描述
        home_desc_config = []
        try:
            with open("data/locations.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                home_desc_config = data.get("home_descriptions", [])
        except Exception as e:
            logger.error(f"Failed to load home descriptions: {e}")

        for i, home_name in enumerate(homes_to_place):
            angle = i * angle_step
            x = int(center_x + radius * math.cos(angle))
            y = int(center_y + radius * math.sin(angle))
            
            # 特定住宅的自定义描述，默认回退为名称
            description = f"{home_name}." # 默认回退
            
            # 查找匹配的描述
            found_match = False
            for config in home_desc_config:
                keywords = config.get("keywords", [])
                if "default" in keywords:
                    continue
                
                for kw in keywords:
                    if kw in home_name:
                        description = config["description"].format(name=home_name)
                        found_match = True
                        break
                if found_match:
                    break
            
            if not found_match:
                # 如果没有匹配则使用默认描述
                for config in home_desc_config:
                    if "default" in config.get("keywords", []):
                        description = config["description"].format(name=home_name)
                        break

            # 将地点添加到地图
            loc = Location(
                name=home_name,
                type=LocationType.HOME,
                description=description,
                coordinates=(x, y),
            )
            self.game_map.add_location(loc)

            # 将住宅与小镇广场连接
            self.game_map.connect_locations(home_name, "小镇广场")

            # 更新居住于此的居民坐标
            if home_name in residences:
                for char in residences[home_name]:
                    char.profile.home_location = home_name
                    char.current_location = home_name
                    char.position = (x, y)

        # 处理居住在 "酒馆" 的居民
        if "酒馆" in residences:
            saloon = self.game_map.get_location("酒馆")
            if saloon:
                for char in residences["酒馆"]:
                    char.profile.home_location = "酒馆"
                    char.current_location = "酒馆"
                    char.position = saloon.coordinates

    def update(self) -> bool:
        self.game_time.tick(minutes=Config.MINUTES_PER_TICK)
        sim_time_var.set(self.game_time.get_display_string())

        # 检查结束条件：达到持续时间且所有人都睡觉
        if self.game_time.current_time >= self.end_time:
            all_sleeping = all(char.is_sleeping() for char in self.characters)
            if all_sleeping:
                logger.info("Simulation finished: Duration reached and all characters are sleeping.")
                return False

        # 检查是否发生交互
        self._handle_interactions()

        for char in self.characters:
            self._update_character(char)
            
        return True

    def stop(self):
        """停止模拟并保存日志。"""
        path = self.logger.save()
        if path:
            logger.info(f"Simulation logs saved to {path}")

    def _handle_interactions(self):
        # 按位置分组居民
        chars_at_loc = {}
        for char in self.characters:
            if char.current_location not in chars_at_loc:
                chars_at_loc[char.current_location] = []
            chars_at_loc[char.current_location].append(char)

        for loc, chars in chars_at_loc.items():
            if len(chars) < 2:
                continue

            # 查找可以交谈的两人
            # 过滤掉睡觉或正在忙碌的居民
            available_chars = [
                c for c in chars if not c.is_thinking and not c.is_sleeping()
            ]

            if len(available_chars) >= 2:
                c1 = available_chars[0]
                c2 = available_chars[1]

                # 检查冷却时间
                pair_key = tuple(sorted((c1.profile.name, c2.profile.name)))
                if pair_key in self.interaction_cooldowns:
                    if (
                        self.game_time.current_time
                        < self.interaction_cooldowns[pair_key]
                    ):
                        continue

                # 避免持续交谈
                if random.random() < (1.0 - Config.INTERACTION_PROBABILITY):
                    continue

                # 触发对话
                self._trigger_conversation(c1, c2)

                # 设置冷却时间
                self.interaction_cooldowns[pair_key] = (
                    self.game_time.current_time
                    + timedelta(minutes=Config.INTERACTION_COOLDOWN_MINUTES)
                )

    def _trigger_conversation(self, c1: Character, c2: Character):
        logger.info(f"{c1.profile.name} 开始与 {c2.profile.name} 对话")

        # 标记为正在思考/忙碌以防止移动
        c1.is_thinking = True
        c2.is_thinking = True
        c1.status = f"正在与 {c2.profile.name} 交谈..."
        c2.status = f"正在与 {c1.profile.name} 交谈..."

        # 异步处理对话
        current_sim_time = self.game_time.get_display_string()
        thread = threading.Thread(target=self._conversation_thread, args=(c1, c2, current_sim_time))
        thread.daemon = True
        thread.start()

    def _conversation_thread(self, c1: Character, c2: Character, sim_time: str):
        sim_time_var.set(sim_time)
        try:
            # 为 C1 生成对话
            system_prompt_c1 = DIALOGUE_SYSTEM_PROMPT.format(
                name=c1.profile.name,
                personality=c1.profile.personality,
                relationships=c1.profile.relationships,
            )

            user_prompt_c1 = DIALOGUE_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=c1.current_location,
                target_name=c2.profile.name,
                context=f"You met {c2.profile.name} at {c1.current_location}. It is {self.game_time.get_full_timestamp()}.",
                memory="\n".join(c1.memory),
            )

            client_c1 = c1.llm_client or self.llm_client
            response_c1 = client_c1.get_json_completion(
                user_prompt_c1, system_prompt=system_prompt_c1
            )
            content_c1 = "..."
            try:
                content_c1 = json.loads(response_c1).get("content", "...")
            except:
                pass

            # 为 C2 生成对话（基于 C1 的内容）
            system_prompt_c2 = DIALOGUE_SYSTEM_PROMPT.format(
                name=c2.profile.name,
                personality=c2.profile.personality,
                relationships=c2.profile.relationships,
            )

            user_prompt_c2 = DIALOGUE_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=c2.current_location,
                target_name=c1.profile.name,
                context=f"You met {c1.profile.name} at {c2.current_location}. {c1.profile.name} said: '{content_c1}'",
                memory="\n".join(c2.memory),
            )

            client_c2 = c2.llm_client or self.llm_client
            response_c2 = client_c2.get_json_completion(
                user_prompt_c2, system_prompt=system_prompt_c2
            )
            content_c2 = "..."
            try:
                content_c2 = json.loads(response_c2).get("content", "...")
            except:
                pass

            # 更新状态以便显示
            c1.status = f"对 {c2.profile.name} 说: {content_c1}"
            c2.status = f"回复 {c1.profile.name} 说: {content_c2}"

            # 记录日志
            logger.info(f"{c1.profile.name}: {content_c1}")
            logger.info(f"{c2.profile.name}: {content_c2}")

            # 记录对话事件
            self.logger.log(
                self.game_time.get_full_timestamp(),
                "dialogue",
                participants=[c1.profile.name, c2.profile.name],
                messages=[
                    {"speaker": c1.profile.name, "content": content_c1},
                    {"speaker": c2.profile.name, "content": content_c2},
                ],
                location=c1.current_location,
            )

            # 更新记忆，使他们记住这次对话
            time_str = self.game_time.get_full_timestamp()
            c1.add_memory(
                f"[{time_str}] I chatted with {c2.profile.name}. I said: '{content_c1}'. They replied: '{content_c2}'."
            )
            c2.add_memory(
                f"[{time_str}] I chatted with {c1.profile.name}. They said: '{content_c1}'. I replied: '{content_c2}'."
            )

            # 保持忙碌一段时间
            duration = Config.CONVERSATION_BUSY_DURATION
            c1.busy_until = self.game_time.current_time + timedelta(minutes=duration)
            c2.busy_until = self.game_time.current_time + timedelta(minutes=duration)

        except Exception as e:
            logger.error(f"Error in conversation: {e}")
        finally:
            c1.is_thinking = False
            c2.is_thinking = False

    def _update_character(self, char: Character):
        if char.busy_until and self.game_time.current_time < char.busy_until:
            return

        if char.is_thinking:
            return

        # 行为规划
        self._plan_character_action_async(char)

    def _plan_character_action_async(self, char: Character):
        char.is_thinking = True
        char.status = "思考中..."
        current_sim_time = self.game_time.get_display_string()
        thread = threading.Thread(
            target=self._plan_character_action_thread, args=(char, current_sim_time)
        )
        thread.daemon = True
        thread.start()

    def _plan_character_action_thread(self, char: Character, sim_time: str):
        sim_time_var.set(sim_time)
        try:
            # 构建包含地点描述的提示词
            location_descriptions = []
            for name, loc in self.game_map.locations.items():
                location_descriptions.append(f"- {name}: {loc.description}")
            locations_str = "\n".join(location_descriptions)

            # 获取其他居民的位置和状态
            other_locs = []
            for c in self.characters:
                if c.profile.name != char.profile.name:
                    # 简单的状态清洗，去掉可能过长的对话内容
                    status_summary = c.status.split('(')[0].strip() if '(' in c.status else c.status
                    other_locs.append(f"{c.profile.name}: {c.current_location} [{status_summary}]")
            other_locs_str = ", ".join(other_locs)

            system_prompt = PLANNING_SYSTEM_PROMPT.format(
                name=char.profile.name,
                age=char.profile.age,
                occupation=char.profile.occupation,
                personality=char.profile.personality,
                features=char.profile.features,
                quote=char.profile.quote,
                relationships=char.profile.relationships,
                locations=locations_str,
                other_characters_locations=other_locs_str,
            )

            # 检查是否有公告板内容（仅在广场可见）
            context_extra = ""
            if char.current_location == "小镇广场":
                square = self.game_map.get_location("小镇广场")
                if square and square.notices:
                    notices_text = "\n".join(
                        [
                            f"- [{n.created_at}] {n.author}: {n.content}"
                            for n in square.notices
                        ]
                    )
                    context_extra = f"\n\nCommunity Board Notices:\n{notices_text}"

            user_prompt = PLANNING_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=char.current_location,
                memory="\n".join(char.memory) + context_extra,
            )

            logger.info(f"Planning for {char.profile.name}...")
            client = char.llm_client or self.llm_client
            response = client.get_json_completion(
                user_prompt, system_prompt=system_prompt
            )

            try:
                plan = json.loads(response)
                action = plan.get("action", "Idle")
                target_location = plan.get("target_location", char.current_location)
                dialogue = plan.get("dialogue", "...")
                emoji = plan.get("emoji", "👤")
                duration = int(plan.get("duration", Config.DEFAULT_ACTION_DURATION))

                # 执行计划
                if target_location != char.current_location:
                    char.move_to(target_location)

                # 处理公告发布
                if "Post Notice" in action and char.current_location == "小镇广场":
                    square = self.game_map.get_location("小镇广场")
                    if square:
                        new_notice = Notice(
                            content=dialogue,
                            author=char.profile.name,
                            created_at=self.game_time.get_full_timestamp(),
                        )
                        square.notices.insert(0, new_notice)  # 最新在最前
                        # 限制公告数量
                        if len(square.notices) > 5:
                            square.notices = square.notices[:5]
                        logger.info(f"Notice posted by {char.profile.name}: {dialogue}")

                char.status = f"{action} ({dialogue})"
                # 确保只使用一个表情符号
                char.emoji = emoji[0] if emoji else "👤"
                char.busy_until = self.game_time.current_time + timedelta(
                    minutes=duration
                )

                logger.info(
                    f"{char.profile.name}: {action} @ {target_location} for {duration}m | Dialogue: {dialogue}"
                )

                # 记录计划
                self.logger.log(
                    self.game_time.get_full_timestamp(),
                    "plan",
                    character=char.profile.name,
                    action=action,
                    target_location=target_location,
                    dialogue=dialogue,
                    emoji=char.emoji,
                    duration=duration,
                )

                # 睡眠阶段触发记忆优化
                # 太短暂的睡眠任务不触发
                if char.is_sleeping() and duration > 120:
                    current_date_str = self.game_time.current_time.strftime("%Y-%m-%d")
                    # 一天仅优化一次
                    if char.last_optimized_date != current_date_str:
                        logger.info(f"Optimizing memory for {char.profile.name}...")
                        char.optimize_memory(self.llm_client, current_date_str)

            except json.JSONDecodeError:
                logger.error(
                    f"Failed to parse LLM response for {char.profile.name}: {response}"
                )
                char.busy_until = self.game_time.current_time + timedelta(
                    minutes=Config.PLANNING_RETRY_DELAY * 2
                )  # 稍后重试
        except Exception as e:
            logger.error(f"Error in planning thread for {char.profile.name}: {e}")
            char.busy_until = self.game_time.current_time + timedelta(
                minutes=Config.PLANNING_RETRY_DELAY
            )
        finally:
            char.is_thinking = False
