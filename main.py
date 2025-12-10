from src.gui.main_window import MainWindow
from src.core.logger import loguru_formatter, get_log_filename
from loguru import logger
import sys
import argparse

# 配置日志
logger.remove()
logger.add(sys.stderr, format=loguru_formatter, level="INFO")
logger.add(get_log_filename(), format=loguru_formatter, level="DEBUG")


def main():
    parser = argparse.ArgumentParser(description="AI Town Simulation")
    parser.add_argument(
        "--replay", type=str, help="Path to a simulation log file to replay"
    )
    args = parser.parse_args()

    logger.info("Starting AI Town...")
    app = MainWindow(replay_log_path=args.replay)
    app.run()


if __name__ == "__main__":
    main()
