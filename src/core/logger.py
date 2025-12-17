import contextvars
import json
import os
from datetime import datetime
from typing import List, Dict, Any

sim_time_var = contextvars.ContextVar("sim_time", default="N/A")


def loguru_formatter(record):
    """Custom formatter for loguru to include simulation time."""
    sim_time = sim_time_var.get()
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>[Sim: "
        + str(sim_time)
        + "]</cyan> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"
    )


def format_timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def get_log_filename():
    t = datetime.now()
    return f"logs/app_{t.strftime('%Y-%m-%d_%H-%M-%S_%f')}.log"


class SimulationLogger:
    def __init__(self, save_dir="logs"):
        self.save_dir = save_dir
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        self.events: List[Dict[str, Any]] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log(self, game_time: str, event_type: str, **kwargs):
        event = {
            "timestamp": game_time,
            "real_time": datetime.now().isoformat(),
            "type": event_type,
            "details": kwargs,
        }
        self.events.append(event)

    def save(self) -> str:
        filename = f"simulation_log_{self.session_id}.json"
        filepath = os.path.join(self.save_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            print(f"Error saving simulation log: {e}")
            return ""
