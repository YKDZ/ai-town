from src.gui.main_window import MainWindow
from src.core.logger import loguru_formatter, get_log_filename
from loguru import logger
import os
import sys
import argparse

# 配置日志
logger.remove()
logger.add(sys.stderr, format=loguru_formatter, level="INFO")


def main():
    parser = argparse.ArgumentParser(description="AI Town Simulation")
    parser.add_argument(
        "--replay", type=str, help="Path to a simulation log file to replay"
    )
    args = parser.parse_args()

    logger.info("Starting AI Town...")
    app = MainWindow(replay_log_path=args.replay)
    # Add file logger using the simulation start time so filenames are consistent
    sim = app.simulation
    session_start = None
    if hasattr(sim, "is_replay") and getattr(sim, "is_replay"):
        # ReplaySimulation defines start_time
        session_start = getattr(sim, "start_time", None)
    else:
        # Live simulation: use game_time current_time as start
        session_start = (
            getattr(sim, "game_time", None).current_time
            if getattr(sim, "game_time", None)
            else None
        )

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    logger.add(get_log_filename(session_start), format=loguru_formatter, level="DEBUG")
    app.run()


if __name__ == "__main__":
    main()
