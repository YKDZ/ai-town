import os


class Config:
    """
    AI Town 模拟配置
    """

    # 模拟总时长（天）
    SIMULATION_DURATION_DAYS = int(os.getenv("SIMULATION_DURATION_DAYS", 3))

    # 游戏分钟 per tick
    MINUTES_PER_TICK = int(os.getenv("MINUTES_PER_TICK", 5))

    # 两个居民对话后的冷却时间（游戏分钟）
    INTERACTION_COOLDOWN_MINUTES = int(os.getenv("INTERACTION_COOLDOWN_MINUTES", 150))

    # 在满足条件时发生交互的概率（[0.0, 1.0]）
    INTERACTION_PROBABILITY = float(os.getenv("INTERACTION_PROBABILITY", 0.4))

    # 对话后居民保持“忙碌”状态的时长（游戏分钟）
    CONVERSATION_BUSY_DURATION = int(os.getenv("CONVERSATION_BUSY_DURATION", 45))

    # 如果 LLM 未指定，计划动作的默认时长（游戏分钟）
    DEFAULT_ACTION_DURATION = int(os.getenv("DEFAULT_ACTION_DURATION", 60))

    # 如果规划失败，重试的延迟时间（游戏分钟）
    PLANNING_RETRY_DELAY = int(os.getenv("PLANNING_RETRY_DELAY", 15))
