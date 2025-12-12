import json
import os
from datetime import datetime
from typing import List, Dict, Any
import contextvars

sim_time_var = contextvars.ContextVar("sim_time", default="N/A")


def loguru_formatter(record):
    """Custom formatter for loguru to include simulation time."""
    sim_time = sim_time_var.get()
    # Format: Time | Level | [Sim: Time] | Module:Line - Message
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>[Sim: "
        + str(sim_time)
        + "]</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
    )


def format_timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def get_log_filename(session_start: datetime = None):
    """Generate a unique log filename based on real time."""
    t = datetime.now()
    return f"logs/app_{t.strftime('%Y-%m-%d_%H-%M-%S_%f')}.log"


class SimulationLogger:
    def __init__(self, save_dir="logs", session_start: datetime = None):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        self.events: List[Dict[str, Any]] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log(self, game_time: str, event_type: str, **kwargs):
        """
        记录一个事件。

        参数:
            game_time: 当前游戏时间字符串。
            event_type: 事件类型（例如 "plan", "dialogue", "action"）。
            **kwargs: 事件的额外详情。
        """
        event = {
            "timestamp": game_time,
            "real_time": datetime.now().isoformat(),
            "type": event_type,
            "details": kwargs,
        }
        self.events.append(event)

    def save(self) -> str:
        """
        将收集的日志保存为 JSON 文件。
        返回保存文件的路径。
        """
        filename = f"simulation_log_{self.session_id}.json"
        filepath = os.path.join(self.save_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            print(f"Error saving simulation log: {e}")
            return ""
