import math
import os

import pygame

from src.core.simulation import Simulation
from src.entities.location import LocationType

# 颜色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (100, 200, 100)
BLUE = (100, 100, 200)
RED = (200, 100, 100)
GRAY = (200, 200, 200)
YELLOW = (255, 255, 100)
DARK_BLUE = (20, 20, 60)  # 夜间颜色
CYAN = (100, 200, 200)


class Renderer:
    def __init__(self, screen: pygame.Surface, simulation: Simulation):
        self.screen = screen
        self.sim = simulation
        self.font = self._get_chinese_font(14)
        self.title_font = self._get_chinese_font(20, bold=True)
        # 加载足够大的字体以便缩放使用
        self.icon_font = self._get_emoji_font(32)

        # 缩放控制
        self.scale_factor = 1.0

        # 平移控制
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.is_dragging = False
        self.last_mouse_pos = (0, 0)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            # 缩放（放大/缩小）
            if event.y > 0:
                self.scale_factor *= 1.1
            elif event.y < 0:
                self.scale_factor /= 1.1

            # 限制缩放范围
            self.scale_factor = max(0.5, min(self.scale_factor, 3.0))

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                # 检查是否在地图区域点击
                mx, my = event.pos
                ui_width = 300
                map_view_width = self.screen.get_width() - ui_width

                # 回放条
                is_replay = hasattr(self.sim, "is_replay") and self.sim.is_replay
                bar_height = 60 if is_replay else 0
                map_view_height = self.screen.get_height() - bar_height

                if mx < map_view_width and my < map_view_height:
                    self.is_dragging = True
                    self.last_mouse_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.is_dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                self.pan_offset_x += dx
                self.pan_offset_y += dy
                self.last_mouse_pos = event.pos

    def _translate_status(self, status: str) -> str:
        # 处理 "Action (Dialogue)" 格式
        if "(" in status and status.endswith(")"):
            # 仅在第一个分隔处拆分以防止意外
            parts = status.split(" (", 1)
            action = parts[0]
            dialogue = parts[1][:-1]  # 去掉末尾的 )

            action_cn = self._translate_simple_action(action)
            return f"{action_cn} ({dialogue})"

        if (
            status.startswith("正在")
            or status.startswith("对")
            or status.startswith("前往")
            or status == "空闲"
            or status == "思考中..."
        ):
            return status

        # 3. 简单动作翻译
        return self._translate_simple_action(status)

    @staticmethod
    def _translate_simple_action(action: str) -> str:
        mapping = {
            "Idle": "空闲",
            "Thinking...": "思考中...",
            "Sleep": "睡觉",
            "Sleeping": "睡觉",
            "Work": "工作",
            "Working": "工作",
            "Eat": "吃饭",
            "Eating": "吃饭",
            "Chat": "聊天",
            "Chatting": "聊天",
            "Walk": "散步",
            "Go to": "前往",
            "Visit": "拜访",
        }

        # 完全匹配
        if action in mapping:
            return mapping[action]

        # 前缀匹配（例如 "Go to Saloon"）
        for k, v in mapping.items():
            if action.startswith(k):
                # 替换前缀，保留后续文本
                return action.replace(k, v, 1)

        return action

    def _get_transform(self):
        # 界面面板宽度
        ui_width = 300
        map_view_width = self.screen.get_width() - ui_width
        map_view_height = self.screen.get_height()

        # 基本尺寸（期望适配的区域）
        # 地图内容大致以 (400,300) 为中心，半径约 250
        # 因此大致覆盖 x=150..650, y=50..550
        # 使用 800x600 的安全区域以包含所有内容
        base_w = 800
        base_h = 600

        # 计算缩放比例
        scale_x = map_view_width / base_w
        scale_y = map_view_height / base_h
        scale = min(scale_x, scale_y) * 0.9 * self.scale_factor

        # 计算偏移，使 (400,300) 位于视图中心
        center_x = map_view_width / 2
        center_y = map_view_height / 2

        offset_x = center_x - 400 * scale + self.pan_offset_x
        offset_y = center_y - 300 * scale + self.pan_offset_y

        return scale, offset_x, offset_y

    def _transform(self, x, y):
        scale, off_x, off_y = self._get_transform()
        return int(x * scale + off_x), int(y * scale + off_y)

    def _get_emoji_font(self, size: int) -> pygame.font.Font:
        font_names = [
            "Segoe UI Emoji",
            "Apple Color Emoji",
            "Noto Color Emoji",
            "Symbola",
        ]
        available_fonts = pygame.font.get_fonts()
        for name in font_names:
            normalized_name = name.lower().replace(" ", "")
            if normalized_name in available_fonts:
                return pygame.font.SysFont(name, size)

        return self._get_chinese_font(size)

    @staticmethod
    def _get_chinese_font(size: int, bold: bool = False) -> pygame.font.Font:
        font_names = [
            "WenQuanYi Micro Hei",
            "Noto Sans CJK SC",
            "Noto Sans CJK",
            "Microsoft YaHei",
            "SimHei",
            "Arial Unicode MS",
        ]

        available_fonts = pygame.font.get_fonts()
        for name in font_names:
            normalized_name = name.lower().replace(" ", "")
            if normalized_name in available_fonts:
                return pygame.font.SysFont(name, size, bold=bold)

        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ]

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return pygame.font.Font(path, size)
                except Exception:
                    continue

        # 最后回退选项
        return pygame.font.SysFont("Arial", size, bold=bold)

    def render(self):
        # 根据时间绘制背景
        if self.sim.game_time.is_night:
            self.screen.fill(DARK_BLUE)
        else:
            self.screen.fill(GREEN)

        self._draw_map()
        self._draw_characters()
        self._draw_status_bubbles_pass()
        self._draw_ui()

        # 如果处于回放模式，绘制回放控制
        if hasattr(self.sim, "is_replay") and self.sim.is_replay:
            self._render_replay_controls()

        self._draw_tooltips()

    def _render_replay_controls(self):
        # 在地图视图底部绘制回放控制栏
        ui_width = 300
        map_view_width = self.screen.get_width() - ui_width
        bar_height = 60
        y = self.screen.get_height() - bar_height

        # 背景
        pygame.draw.rect(
            self.screen, (240, 240, 240), (0, y, map_view_width, bar_height)
        )
        pygame.draw.line(self.screen, GRAY, (0, y), (map_view_width, y), 1)

        # 进度条
        progress = 0.0
        if self.sim.start_time and self.sim.end_time:
            total = (self.sim.end_time - self.sim.start_time).total_seconds()
            current = (self.sim.current_time - self.sim.start_time).total_seconds()
            if total > 0:
                progress = max(0, min(1, current / total))

        bar_x = 20
        bar_y = y + 20
        bar_w = map_view_width - 40
        bar_h = 10

        # 绘制进度条背景
        pygame.draw.rect(self.screen, GRAY, (bar_x, bar_y, bar_w, bar_h))
        # 绘制当前进度
        pygame.draw.rect(
            self.screen, BLUE, (bar_x, bar_y, int(bar_w * progress), bar_h)
        )

        # 绘制时间文本
        time_str = self.sim.game_time.get_full_timestamp()
        status_str = "PAUSED" if self.sim.paused else "PLAYING"
        text = self.font.render(
            f"回放: {time_str} | {status_str} | 速度: {self.sim.speed:.1f}x",
            True,
            BLACK,
        )
        self.screen.blit(text, (bar_x, y + 35))

        # 绘制控制提示
        help_text = self.font.render(
            "[空格] 暂停/播放  [箭头] 查找/速度", True, (100, 100, 100)
        )
        self.screen.blit(help_text, (map_view_width - 300, y + 35))

    def _draw_map(self):
        for name, loc in self.sim.game_map.locations.items():
            # 坐标变换
            x, y = self._transform(*loc.coordinates)

            color = GRAY
            if loc.type == LocationType.SQUARE:
                color = YELLOW
            elif loc.type == LocationType.SALOON:
                color = RED
            elif loc.type == LocationType.HOME:
                color = BLUE
            elif loc.type == LocationType.LIBRARY:
                color = CYAN

            # 绘制地点
            # 略微缩放尺寸以保持可读性
            scale, _, _ = self._get_transform()
            size = int(60 * scale)
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)

            # 绘制标签
            text = self.font.render(
                name, True, WHITE if self.sim.game_time.is_night else BLACK
            )
            text_rect = text.get_rect(center=(x, y + size // 2 + 10))
            self.screen.blit(text, text_rect)

            # 绘制连接线
            for connected_name in loc.connected_locations:
                connected_loc = self.sim.game_map.get_location(connected_name)
                if connected_loc:
                    cx, cy = self._transform(*connected_loc.coordinates)
                    pygame.draw.line(self.screen, BLACK, (x, y), (cx, cy), 1)

            # 绘制公告板图标（仅在广场）
            if loc.type == LocationType.SQUARE:
                board_x = x + size // 2 + 10
                board_y = y - size // 2

                # 绘制板子
                board_rect = pygame.Rect(board_x, board_y, 20 * scale, 15 * scale)
                pygame.draw.rect(self.screen, (139, 69, 19), board_rect)  # 棕色
                pygame.draw.rect(self.screen, BLACK, board_rect, 1)

                # 如果有公告，画个感叹号
                if hasattr(loc, "notices") and loc.notices:
                    excl = self.font.render("!", True, YELLOW)
                    self.screen.blit(excl, (board_x + 5 * scale, board_y - 15 * scale))

    def _draw_characters(self):
        # 按位置分组居民，避免重叠
        chars_at_loc = {}
        for char in self.sim.characters:
            if char.current_location not in chars_at_loc:
                chars_at_loc[char.current_location] = []
            chars_at_loc[char.current_location].append(char)

        for loc_name, chars in chars_at_loc.items():
            loc = self.sim.game_map.get_location(loc_name)
            if not loc:
                continue

            base_x, base_y = self._transform(*loc.coordinates)
            scale, _, _ = self._get_transform()

            # 识别正在交互的居民以分组显示
            interactions = {}
            processed = set()

            for char in chars:
                if char in processed:
                    continue

                partner_name = None
                if "Talking to " in char.status:
                    partner_name = char.status.split("Talking to ")[1].replace(
                        "...", ""
                    )
                elif "正在与" in char.status:
                    try:
                        # "正在与 {name} 交谈..."
                        partner_name = char.status.split("正在与 ")[1].split(" 交谈")[0]
                    except IndexError:
                        pass
                elif "Said to " in char.status:
                    try:
                        partner_name = char.status.split("Said to ")[1].split(":")[0]
                    except IndexError:
                        pass
                elif "对" in char.status and "说:" in char.status:
                    try:
                        # 格式: "对 {name} 说: ..."
                        partner_name = char.status.split("对 ")[1].split(" 说:")[0]
                    except IndexError:
                        pass
                elif "回复" in char.status and "说:" in char.status:
                    try:
                        # 格式: "回复 {name} 说: ..."
                        partner_name = char.status.split("回复 ")[1].split(" 说:")[0]
                    except IndexError:
                        pass

                if partner_name:
                    partner = next(
                        (c for c in chars if c.profile.name == partner_name), None
                    )
                    if partner and partner not in processed:
                        interactions[char] = partner
                        processed.add(char)
                        processed.add(partner)

            # 分为单人和成对两类
            singles = [c for c in chars if c not in processed]
            pairs = []
            for c1, c2 in interactions.items():
                pairs.append((c1, c2))

            # 布局计算
            total_groups = len(singles) + len(pairs)
            radius = 25 * scale

            # 人数较多时增加半径
            if total_groups > 4:
                radius = 35 * scale

            angle_step = 2 * math.pi / max(1, total_groups)
            current_angle = 0

            # 计算元素缩放（图标增长速度低于地图）
            # 计算元素缩放公式：element_scale ~ scale / scale_factor * (scale_factor ^ 0.7)
            element_scale = scale
            if self.scale_factor > 0:
                element_scale = scale / self.scale_factor * (self.scale_factor**0.7)

            # 绘制单人
            for char in singles:
                if total_groups == 1:
                    x, y = base_x, base_y
                else:
                    x = base_x + radius * math.cos(current_angle)
                    y = base_y + radius * math.sin(current_angle)

                self._draw_single_char(char, x, y, element_scale)
                current_angle += angle_step

            # 绘制成对居民
            for c1, c2 in pairs:
                # 成对居民的中心
                if total_groups == 1:  # 仅有一对
                    cx, cy = base_x, base_y
                else:
                    cx = base_x + radius * math.cos(current_angle)
                    cy = base_y + radius * math.sin(current_angle)

                # 从中心点略微偏移
                # 确保间距至少能容纳图标
                sep = 10 * max(scale, element_scale)
                self._draw_single_char(c1, cx - sep, cy, element_scale)
                self._draw_single_char(c2, cx + sep, cy, element_scale)

                current_angle += angle_step

    def _draw_single_char(self, char, char_x, char_y, scale):
        char.render_pos = (char_x, char_y)

        # 绘制居民图标
        icon = char.profile.icon
        text = self.icon_font.render(icon, True, BLACK)

        # 动态缩放图标以适配圆形背景
        target_size = max(1, int(15 * scale))
        try:
            text = pygame.transform.smoothscale(text, (target_size, target_size))
        except ValueError:
            text = pygame.transform.scale(text, (target_size, target_size))

        text_rect = text.get_rect(center=(char_x, char_y))

        # 绘制背景圆以提升可见性
        radius = 10 * scale
        pygame.draw.circle(self.screen, WHITE, (char_x, char_y), radius)
        pygame.draw.circle(self.screen, BLACK, (char_x, char_y), radius, 1)

        self.screen.blit(text, text_rect)

    def _draw_status_bubbles_pass(self):
        scale, _, _ = self._get_transform()

        # 计算元素缩放（图标增长速度低于地图）
        element_scale = scale
        if self.scale_factor > 0:
            element_scale = scale / self.scale_factor * (self.scale_factor**0.7)

        for char in self.sim.characters:
            if hasattr(char, "render_pos"):
                x, y = char.render_pos
                self._draw_status_bubble(char, x, y, element_scale)

    def _draw_status_bubble(self, char, x, y, scale):
        # 优先使用 LLM 返回的表情，若无则使用规则判断
        status_icon = getattr(char, "emoji", None)

        # 回退逻辑
        if not status_icon or status_icon == "👤":
            if char.is_sleeping():
                status_icon = "💤"
            elif char.is_talking():
                status_icon = "💬"
            elif char.is_thinking_status():
                status_icon = "💭"
            elif char.is_working():
                status_icon = "⚒️"
            elif char.is_eating():
                status_icon = "🍽️"

        if status_icon:
            # 气泡位置：位于居民上方并略向右
            bubble_x = x + 10 * scale
            bubble_y = y - 15 * scale

            # 绘制表情图标
            icon_surf = self.icon_font.render(status_icon, True, BLACK)

            # 计算圆角矩形（胶囊形）尺寸
            # 气泡基础高度（较小）
            bubble_h = 18 * scale
            # 文本的长宽比
            aspect = icon_surf.get_width() / icon_surf.get_height()

            # 目标文本高度（略小于气泡高度）
            text_h = int(bubble_h * 0.7)
            text_w = int(text_h * aspect)

            # 气泡宽度基于文本宽度加内边距
            padding = 5 * scale
            bubble_w = text_w + padding * 2

            # 确保最小宽度（单个表情时接近圆形）
            min_w = bubble_h
            if bubble_w < min_w:
                bubble_w = min_w

            # 气泡矩形
            rect = pygame.Rect(0, 0, bubble_w, bubble_h)
            rect.center = (bubble_x, bubble_y)

            # 绘制圆角矩形
            border_radius = int(bubble_h / 2)

            pygame.draw.rect(self.screen, WHITE, rect, border_radius=border_radius)
            pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=border_radius)

            # 缩放并绘制文本
            try:
                icon_surf = pygame.transform.smoothscale(icon_surf, (text_w, text_h))
            except ValueError:
                icon_surf = pygame.transform.scale(icon_surf, (text_w, text_h))

            icon_rect = icon_surf.get_rect(center=rect.center)
            self.screen.blit(icon_surf, icon_rect)

    def _draw_tooltips(self):
        mouse_pos = pygame.mouse.get_pos()

        # 1. Check for Notice Board tooltip (Town Square)
        square = self.sim.game_map.get_location("小镇广场")
        if square:
            # Re-calculate board position (same logic as _draw_map)
            x, y = self._transform(*square.coordinates)
            scale, _, _ = self._get_transform()
            size = int(60 * scale)
            board_x = x + size // 2 + 10
            board_y = y - size // 2
            board_rect = pygame.Rect(board_x, board_y, 20 * scale, 15 * scale)

            if board_rect.collidepoint(mouse_pos):
                self._draw_notice_board_tooltip(square, mouse_pos)
                return  # Prioritize board tooltip

        # 2. Check for Character tooltips
        for char in self.sim.characters:
            if hasattr(char, "render_pos"):
                cx, cy = char.render_pos
                # 检查与居民周围小半径是否碰撞
                if (mouse_pos[0] - cx) ** 2 + (
                    mouse_pos[1] - cy
                ) ** 2 < 100:  # 10px 半径的平方
                    self._draw_character_tooltip(char, mouse_pos)
                    break  # 只显示一个提示框

    def _draw_notice_board_tooltip(self, location, pos):
        lines = ["=== 社区公告板 ==="]
        if hasattr(location, "notices") and location.notices:
            for notice in location.notices:
                lines.append(f"[{notice.created_at}] {notice.author}:")
                # Simple wrap for content
                content = notice.content
                while len(content) > 20:
                    lines.append("  " + content[:20])
                    content = content[20:]
                lines.append("  " + content)
                lines.append("-" * 20)
        else:
            lines.append("(暂无公告)")

        self._draw_tooltip_box(lines, pos)

    def _wrap_text(self, text: str, max_width: int):
        """
        中英文通用的像素级自动换行
        """
        lines = []
        current_line = ""

        for ch in text:
            test_line = current_line + ch
            if self.font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = ch

        if current_line:
            lines.append(current_line)

        return lines

    def _draw_character_tooltip(self, char, pos):
        max_text_width = 300

        lines = [
            f"姓名: {char.profile.name}",
        ]

        # 状态可能很长，单独处理
        status_text = f"状态: {self._translate_status(char.status)}"
        status_lines = self._wrap_text(status_text, max_text_width)
        lines.extend(status_lines)

        lines.extend(
            [
                f"位置: {char.current_location}",
                f"职业: {char.profile.occupation}",
            ]
        )

        self._draw_tooltip_box(lines, pos)

    def _draw_tooltip_box(self, lines, pos):
        # 计算提示框大小
        max_width = 0
        height = 0
        surfaces = []
        for line in lines:
            surf = self.font.render(line, True, BLACK)
            max_width = max(max_width, surf.get_width())
            height += surf.get_height() + 2
            surfaces.append(surf)

        box_rect = pygame.Rect(pos[0] + 10, pos[1] + 10, max_width + 10, height + 10)

        # 确保提示框在屏幕内
        if box_rect.right > self.screen.get_width():
            box_rect.x -= box_rect.width + 20
        if box_rect.bottom > self.screen.get_height():
            box_rect.y -= box_rect.height + 20

        pygame.draw.rect(self.screen, (255, 255, 220), box_rect)
        pygame.draw.rect(self.screen, BLACK, box_rect, 1)

        y = box_rect.y + 5
        for surf in surfaces:
            self.screen.blit(surf, (box_rect.x + 5, y))
            y += surf.get_height() + 2

    def _draw_ui(self):
        # Display time with weekday
        time_str = self.sim.game_time.get_display_string()
        time_surf = self.title_font.render(time_str, True, WHITE)
        self.screen.blit(time_surf, (10, 10))

        # 居民状态列表（侧边栏）
        panel_x = self.screen.get_width() - 300  # 更宽的面板
        pygame.draw.rect(
            self.screen, (50, 50, 50), (panel_x, 0, 300, self.screen.get_height())
        )

        y = 10
        header = self.title_font.render("居民状态", True, WHITE)
        self.screen.blit(header, (panel_x + 10, y))
        y += 30

        for char in self.sim.characters:
            name_surf = self.font.render(f"{char.profile.name}:", True, YELLOW)
            self.screen.blit(name_surf, (panel_x + 10, y))
            y += 15

            # 处理多行状态（尤其是对话）
            status_text = self._translate_status(char.status)
            # 简单的状态换行逻辑
            words = status_text.split(" ")
            line = ""
            for word in words:
                test_line = line + word + " "
                if self.font.size(test_line)[0] < 280:
                    line = test_line
                else:
                    status_surf = self.font.render(line, True, WHITE)
                    self.screen.blit(status_surf, (panel_x + 20, y))
                    y += 15
                    line = word + " "
            if line:
                status_surf = self.font.render(line, True, WHITE)
                self.screen.blit(status_surf, (panel_x + 20, y))
                y += 25
