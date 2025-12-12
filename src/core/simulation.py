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
from src.core.id_mapper import init_id_mappings, get_id_manager
from src.core.response_validator import (
    LLMResponseValidator,
    ContextBuilder,
    ResponseConverter,
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
        start_month = 7
        start_day = 28
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

        # 计算结束时间：模拟从开始时间持续duration_days天，结束在最后一天的22:00
        # 例如：从7月28日6点开始，持续2天，则结束在7月30日22点
        end_day = self.game_time.current_time + timedelta(days=duration_days)
        self.end_time = end_day.replace(hour=22, minute=0, second=0, microsecond=0)

        self.interaction_cooldowns = {}
        # Use simulation start time for logger session id
        self.logger = SimulationLogger(session_start=self.game_time.current_time)

        self._load_characters()
        self._init_id_mappings()
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

    def _init_id_mappings(self):
        """初始化规范 ID 映射系统"""
        try:
            # 加载角色数据
            with open(self.humanity_path, "r", encoding="utf-8") as f:
                characters_data = json.load(f)

            # 加载位置数据
            with open("data/locations.json", "r", encoding="utf-8") as f:
                locations_data = json.load(f)

            # 初始化 ID 映射
            manager = init_id_mappings(characters_data, locations_data)

            # 注册标准动作
            actions = [
                ("act_move", "移动", "Move"),
                ("act_chat", "聊天", "Chat"),
                ("act_sleep", "睡觉", "Sleep"),
                ("act_work", "工作", "Work"),
                ("act_idle", "空闲", "Idle"),
                ("act_post_notice", "发布公告", "Post Notice"),
                ("act_clean", "打扫", "Clean"),
                ("act_read", "阅读", "Read"),
                ("act_eat", "吃饭", "Eat"),
                ("act_drink", "喝酒", "Drink"),
                ("act_play", "玩耍", "Play"),
                ("act_shop", "购物", "Shop"),
                ("act_explore", "探索", "Explore"),
            ]
            for act_id, zh, en in actions:
                manager.register_action(act_id, zh, en)

            logger.info("ID 映射已初始化")
        except Exception as e:
            logger.error(f"Failed to initialize ID mappings: {e}")
            raise

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
        # 使用 ID 判断是否为酒馆
        id_manager = get_id_manager()
        
        homes_to_place = []
        for r in residences.keys():
            loc_id = id_manager.loc_id_from_zh(r)
            if loc_id != "loc_saloon":
                homes_to_place.append(r)
                
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
            description = f"{home_name}."  # 默认回退

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

            # Find English name for home
            english_home_name = None
            if home_name in residences and residences[home_name]:
                english_home_name = residences[home_name][
                    0
                ].profile.english_home_location

            # 将地点添加到地图
            loc = Location(
                name=home_name,
                english_name=english_home_name,
                type=LocationType.HOME,
                description=description,
                coordinates=(x, y),
            )
            self.game_map.add_location(loc)

            # Register home ID if English name is available
            if english_home_name:
                id_manager = get_id_manager()
                canonical_id = f"loc_{english_home_name.lower().replace(' ', '_')}"
                try:
                    id_manager.register_location(
                        canonical_id, home_name, english_home_name
                    )
                except ValueError:
                    # Ignore if already registered (e.g. Saloon is both a static location and a home)
                    pass

            # 将住宅与小镇广场连接
            self.game_map.connect_locations(home_name, "小镇广场")

            # 更新居住于此的居民坐标
            if home_name in residences:
                for char in residences[home_name]:
                    char.profile.home_location = home_name
                    char.current_location = home_name
                    # 记录规范 ID
                    try:
                        id_manager = get_id_manager()
                        char.current_location_id = id_manager.loc_id_from_zh(home_name)
                    except Exception:
                        pass
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

        # 处于最后一天晚上（20点之后）且所有人都睡觉时结束模拟
        early_end_threshold = self.end_time - timedelta(hours=2)  # 22:00 - 2小时 = 20:00
        if self.game_time.current_time >= early_end_threshold:
            all_sleeping = all(char.is_sleeping() for char in self.characters)
            if all_sleeping:
                logger.info(
                    "Simulation finished: All characters are sleeping on the last day."
                )
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
                # 动态冷却：如果当前位置人数较多（>=3），视为社交聚会，大幅缩短冷却时间（例如 15 分钟）
                # 否则使用默认冷却时间（例如 60 分钟）
                cooldown_minutes = Config.INTERACTION_COOLDOWN_MINUTES
                if len(chars) >= 3:
                    cooldown_minutes = 15
                
                self.interaction_cooldowns[pair_key] = (
                    self.game_time.current_time
                    + timedelta(minutes=cooldown_minutes)
                )

    def _build_context_info(self, exclude_char: Character = None):
        """构建位置和其他居民的上下文信息，用于 LLM 提示。

        Args:
            exclude_char: 要排除的角色（通常是当前规划的角色）

        Returns:
            tuple: (locations_str, other_locs_str)
        """
        id_manager = get_id_manager()

        # 构建位置描述
        location_descriptions = []
        for name, loc in self.game_map.locations.items():
            loc_id = id_manager.loc_id_from_zh(name)
            if loc_id:
                loc_name_display = f"{loc_id} ({name})"
            else:
                loc_name_display = (
                    f"{loc.english_name} ({name})"
                    if getattr(loc, "english_name", None)
                    else name
                )
            location_descriptions.append(f"- {loc_name_display}: {loc.description}")
        locations_str = "\n".join(location_descriptions)

        # 构建其他居民的位置和状态
        other_locs = []
        for c in self.characters:
            # 如果指定了排除角色，则跳过该角色
            if exclude_char and c.profile.name == exclude_char.profile.name:
                continue

            c_name_display = (
                f"{c.profile.english_name} ({c.profile.name})"
                if c.profile.english_name
                else c.profile.name
            )
            c_loc = self.game_map.get_location(c.current_location)
            c_loc_name = c.current_location
            if c_loc and getattr(c_loc, "english_name", None):
                c_loc_name = f"{c_loc.english_name} ({c.current_location})"

            status_summary = (
                c.status.split("(")[0].strip() if "(" in c.status else c.status
            )
            other_locs.append(f"- {c_name_display}: {c_loc_name} [{status_summary}]")

        other_locs_str = "\n".join(other_locs)
        return locations_str, other_locs_str

    def _trigger_conversation(self, c1: Character, c2: Character):
        logger.info(f"{c1.profile.name} 开始与 {c2.profile.name} 对话")

        # 标记为正在思考/忙碌以防止移动
        c1.is_thinking = True
        c2.is_thinking = True
        c1.status = f"正在与 {c2.profile.name} 交谈..."
        c2.status = f"正在与 {c1.profile.name} 交谈..."
        
        # 设置动作 ID
        c1.last_action_id = "act_chat"
        c2.last_action_id = "act_chat"

        # 异步处理对话
        current_sim_time = self.game_time.get_display_string()
        thread = threading.Thread(
            target=self._conversation_thread, args=(c1, c2, current_sim_time)
        )
        thread.daemon = True
        thread.start()

    def _conversation_thread(self, c1: Character, c2: Character, sim_time: str):
        sim_time_var.set(sim_time)
        try:
            id_manager = get_id_manager()
            c1_id = id_manager.char_id_from_zh(c1.profile.name)
            c2_id = id_manager.char_id_from_zh(c2.profile.name)

            c1_name_display = (
                f"{c1.profile.english_name} ({c1.profile.name})"
                if c1.profile.english_name
                else c1.profile.name
            )
            c2_name_display = (
                f"{c2.profile.english_name} ({c2.profile.name})"
                if c2.profile.english_name
                else c2.profile.name
            )

            # 获取位置和其他居民的上下文（对话包含所有人）
            locations_str, other_locs_str = self._build_context_info()

            loc = self.game_map.get_location(c1.current_location)
            loc_name_display = (
                f"{loc.english_name} ({c1.current_location})"
                if loc and getattr(loc, "english_name", None)
                else c1.current_location
            )
            loc_id = id_manager.loc_id_from_zh(c1.current_location)

            # 为 C1 生成对话
            system_prompt_c1 = DIALOGUE_SYSTEM_PROMPT.format(
                name=c1_name_display,
                char_id=c1_id,
                personality=c1.profile.personality,
                relationships=c1.profile.relationships,
                locations=locations_str,
                other_characters_locations=other_locs_str,
            )

            user_prompt_c1 = DIALOGUE_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=loc_name_display,
                location_id=loc_id,
                target_name=c2_name_display,
                context=f"You met {c2_name_display} at {loc_name_display}. It is {self.game_time.get_full_timestamp()}.",
                memory="\n".join(c1.memory),
            )

            client_c1 = c1.llm_client or self.llm_client
            response_c1 = client_c1.get_json_completion(
                user_prompt_c1, system_prompt=system_prompt_c1
            )
            content_c1 = "..."
            try:
                response_json = json.loads(response_c1)
                validated_response = LLMResponseValidator.validate_dialogue_response(
                    response_json
                )
                content_c1 = validated_response.get("content", "...")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    f"Failed to validate dialogue response for {c1.profile.name}: {e}"
                )
                try:
                    content_c1 = json.loads(response_c1).get("content", "...")
                except:
                    pass

            # 为 C2 生成对话（基于 C1 的内容）
            system_prompt_c2 = DIALOGUE_SYSTEM_PROMPT.format(
                name=c2_name_display,
                char_id=c2_id,
                personality=c2.profile.personality,
                relationships=c2.profile.relationships,
                locations=locations_str,
                other_characters_locations=other_locs_str,
            )

            user_prompt_c2 = DIALOGUE_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=loc_name_display,
                location_id=loc_id,
                target_name=c1_name_display,
                context=f"You met {c1_name_display} at {loc_name_display}. {c1_name_display} said: '{content_c1}'",
                memory="\n".join(c2.memory),
            )

            client_c2 = c2.llm_client or self.llm_client
            response_c2 = client_c2.get_json_completion(
                user_prompt_c2, system_prompt=system_prompt_c2
            )
            content_c2 = "..."
            try:
                response_json = json.loads(response_c2)
                validated_response = LLMResponseValidator.validate_dialogue_response(
                    response_json
                )
                content_c2 = validated_response.get("content", "...")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    f"Failed to validate dialogue response for {c2.profile.name}: {e}"
                )
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
            id_manager = get_id_manager()
            char_id = id_manager.char_id_from_zh(char.profile.name)

            # 构建位置和其他居民的上下文信息
            locations_str, other_locs_str = self._build_context_info(exclude_char=char)

            # 构建动作列表
            actions_list = []
            for act_id, zh in id_manager.actions.id_to_zh.items():
                en = id_manager.actions.id_to_en.get(act_id, "")
                actions_list.append(f"- {act_id} ({en}/{zh})")
            actions_str = "\n".join(actions_list)

            char_name_display = (
                f"{char.profile.english_name} ({char.profile.name})"
                if char.profile.english_name
                else char.profile.name
            )

            system_prompt = PLANNING_SYSTEM_PROMPT.format(
                name=char_name_display,
                char_id=char_id,
                age=char.profile.age,
                occupation=char.profile.occupation,
                personality=char.profile.personality,
                features=char.profile.features,
                relationships=char.profile.relationships,
                locations=locations_str,
                other_characters_locations=other_locs_str,
                actions=actions_str,
            )

            # 检查是否有公告板内容
            context_extra = ""
            # 使用 ID 判断是否在小镇广场
            if char.current_location_id == "loc_town_square":
                square = self.game_map.get_location("小镇广场")
                if square and square.notices:
                    notices_text = "\n".join(
                        [
                            f"- [{n.created_at}] {n.author}: {n.content}"
                            for n in square.notices
                        ]
                    )
                    context_extra = f"\n\nCommunity Board Notices:\n{notices_text}"

            current_loc = self.game_map.get_location(char.current_location)
            current_loc_name = char.current_location
            if current_loc and current_loc.english_name:
                current_loc_name = (
                    f"{current_loc.english_name} ({char.current_location})"
                )

            loc_id = id_manager.loc_id_from_zh(char.current_location)

            user_prompt = PLANNING_USER_PROMPT.format(
                date=self.game_time.get_day_string(),
                time=self.game_time.get_time_string(),
                location=current_loc_name,
                location_id=loc_id,
                memory="\n".join(char.memory) + context_extra,
            )

            logger.info(f"Planning for {char.profile.name}...")
            client = char.llm_client or self.llm_client
            response = client.get_json_completion(
                user_prompt, system_prompt=system_prompt
            )

            try:
                plan = json.loads(response)

                # 使用验证器验证和转换 LLM 响应
                # 这会自动将 target_location ID 转换为中文名称
                try:
                    validated_plan = LLMResponseValidator.validate_planning_response(
                        plan, current_char_id=None
                    )
                    action = validated_plan["action"]
                    target_location = validated_plan["target_location"]
                    dialogue = validated_plan["dialogue"]
                    emoji = validated_plan["emoji"]
                    duration = validated_plan["duration"]
                except ValueError as ve:
                    logger.warning(
                        f"Validation failed for {char.profile.name}: {ve}. "
                        f"Using fallback values from raw response."
                    )
                    # 回退到原始处理
                    action = plan.get("action", "Idle")
                    target_location_input = plan.get(
                        "target_location", char.current_location
                    )

                    # 尝试从 ID 转换
                    if target_location_input.startswith("loc_"):
                        manager = get_id_manager()
                        converted_loc = manager.loc_zh_from_id(target_location_input)
                        target_location = (
                            converted_loc if converted_loc else target_location_input
                        )
                    else:
                        target_location = target_location_input

                    dialogue = plan.get("dialogue", "...")
                    emoji = plan.get("emoji", "👤")[0] if plan.get("emoji") else "👤"
                    duration = int(plan.get("duration", Config.DEFAULT_ACTION_DURATION))

                # 尝试将 action 解析为规范 ID
                action_id = action
                if not action.startswith("act_"):
                    # 尝试从中文查找 ID
                    aid = id_manager.act_id_from_zh(action)
                    if not aid:
                        # 尝试从英文查找 ID
                        aid = id_manager.act_id_from_en(action)
                    
                    if aid:
                        action_id = aid
                
                char.last_action_id = action_id

                # 执行计划
                if target_location != char.current_location:
                    char.move_to(target_location)
                else:
                    # 即使不移动也更新当前地点的规范 ID（防止初始 None）
                    try:
                        if char.current_location_id is None:
                            char.current_location_id = id_manager.loc_id_from_zh(target_location)
                    except Exception:
                        pass

                # 处理公告发布
                # 使用规范 ID 检查
                is_posting_notice = (action_id == "act_post_notice")

                # 检查地点：使用 ID 判断
                if is_posting_notice and char.current_location_id == "loc_town_square":
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

                # 获取显示名称
                action_display = id_manager.get_action_display_name(action_id)

                char.status = f"{action_display} ({dialogue})"
                # 确保只使用一个表情符号
                char.emoji = emoji[0] if emoji else "👤"
                char.busy_until = self.game_time.current_time + timedelta(
                    minutes=duration
                )

                logger.info(
                    f"{char.profile.name}: {action_display} @ {target_location} for {duration}m | Dialogue: {dialogue}"
                )

                # 记录计划
                self.logger.log(
                    self.game_time.get_full_timestamp(),
                    "plan",
                    character=char.profile.name,
                    action=action_display, # 记录显示名称
                    action_id=action_id,   # 同时也记录 ID 以便调试
                    target_location=target_location,
                    dialogue=dialogue,
                    emoji=char.emoji,
                    duration=duration,
                )

                # 睡眠阶段触发记忆优化
                # 太短暂的睡眠任务不触发
                if char.is_sleeping() and duration > 120:
                    current_date_str = self.game_time.get_day_string()
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
