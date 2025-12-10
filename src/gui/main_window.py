import pygame
import sys
import os
from src.core.simulation import Simulation
from src.core.replay import ReplaySimulation
from src.gui.renderer import Renderer


class MainWindow:
    def __init__(self, replay_log_path: str = None):
        pygame.init()
        self.width = 1024
        self.height = 768
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE
        )
        pygame.display.set_caption("AI Town - Stardew Valley Edition")

        self.clock = pygame.time.Clock()
        self.running = True
        self.frame_count = 0

        # 初始化模拟
        if replay_log_path:
            print(f"Starting in Replay Mode with log: {replay_log_path}")
            self.simulation = ReplaySimulation(
                replay_log_path, humanity_path="data/characters.json"
            )
        else:
            self.simulation = Simulation(humanity_path="data/characters.json")

        self.renderer = Renderer(self.screen, self.simulation)

    def run(self):
        while self.running:
            self._handle_events()
            self._update()
            self._render()
            self.clock.tick(30)  # 30 fps
            self.frame_count += 1

        # 退出前如果是真实模拟则保存日志
        if isinstance(self.simulation, Simulation):
            self.simulation.stop()

        pygame.quit()
        sys.exit()

    def _handle_events(self):
        for event in pygame.event.get():
            # 将事件传递给 renderer（例如用于缩放）
            self.renderer.handle_event(event)

            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode(
                    (self.width, self.height), pygame.RESIZABLE
                )
                self.renderer.screen = self.screen
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    # 加载最新回放
                    self._load_latest_replay()

                # 回放控制
                if hasattr(self.simulation, "is_replay") and self.simulation.is_replay:
                    if event.key == pygame.K_SPACE:
                        self.simulation.paused = not self.simulation.paused
                    elif event.key == pygame.K_UP:
                        self.simulation.speed = min(10.0, self.simulation.speed + 0.5)
                    elif event.key == pygame.K_DOWN:
                        self.simulation.speed = max(0.5, self.simulation.speed - 0.5)
                    elif event.key == pygame.K_RIGHT:
                        # 向前跳 10 分钟
                        from datetime import timedelta

                        if self.simulation.current_time and self.simulation.end_time:
                            self.simulation.current_time = min(
                                self.simulation.end_time,
                                self.simulation.current_time + timedelta(minutes=10),
                            )
                            self.simulation.game_time.current_time = (
                                self.simulation.current_time
                            )
                            self.simulation._update_character_states()
                    elif event.key == pygame.K_LEFT:
                        # 向后跳 10 分钟
                        from datetime import timedelta

                        if self.simulation.current_time and self.simulation.start_time:
                            self.simulation.current_time = max(
                                self.simulation.start_time,
                                self.simulation.current_time - timedelta(minutes=10),
                            )
                            self.simulation.game_time.current_time = (
                                self.simulation.current_time
                            )
                            self.simulation._update_character_states()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 检查是否点击了时间轴
                if hasattr(self.simulation, "is_replay") and self.simulation.is_replay:
                    mx, my = pygame.mouse.get_pos()
                    ui_width = 300
                    map_view_width = self.screen.get_width() - ui_width
                    bar_height = 60
                    y = self.screen.get_height() - bar_height

                    if my > y and mx < map_view_width:
                        # 点击在控制区域
                        bar_x = 20
                        bar_w = map_view_width - 40
                        if bar_x <= mx <= bar_x + bar_w:
                            progress = (mx - bar_x) / bar_w
                            self.simulation.set_time(progress)

    def _load_latest_replay(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            print("No logs directory found.")
            return

        files = [
            f
            for f in os.listdir(log_dir)
            if f.startswith("simulation_log_") and f.endswith(".json")
        ]
        if not files:
            print("No log files found.")
            return

        # 按名称排序（名称中包含时间戳）
        files.sort(reverse=True)
        latest_log = os.path.join(log_dir, files[0])
        print(f"Loading replay: {latest_log}")

        # 如果当前正在运行则停止模拟
        if isinstance(self.simulation, Simulation):
            self.simulation.stop()

        # 切换到回放模式
        self.simulation = ReplaySimulation(latest_log)
        self.renderer.sim = self.simulation

    def _update(self):
        # 每 30 帧（1 秒）更新一次模拟
        # 即每真实秒钟推进 1 个游戏分钟（配置可改）
        if self.frame_count % 30 == 0 or (
            hasattr(self.simulation, "is_replay") and self.simulation.is_replay
        ):
            should_continue = self.simulation.update()
            if should_continue is False:
                # 模拟结束
                self.running = False

    def _render(self):
        self.renderer.render()
        pygame.display.flip()
