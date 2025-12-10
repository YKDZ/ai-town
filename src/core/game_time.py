from datetime import datetime, timedelta


class GameTime:
    def __init__(self, start_year=2025, start_month=1, start_day=1, start_hour=6):
        self.current_time = datetime(start_year, start_month, start_day, start_hour, 0)
        self.day_count = 1

    def tick(self, minutes=3):
        self.current_time += timedelta(minutes=minutes)

    @property
    def is_night(self):
        return self.current_time.hour >= 22 or self.current_time.hour < 6

    def __str__(self):
        return self.current_time.strftime("%Y-%m-%d %H:%M")

    def get_time_string(self):
        return self.current_time.strftime("%H:%M")

    def get_day_string(self):
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        wd = weekdays[self.current_time.weekday()]
        return f"{self.current_time.strftime('%Y年%m月%d日')} {wd}"

    def get_full_timestamp(self):
        return self.current_time.strftime("%Y-%m-%d %H:%M")

    def get_display_string(self):
        """Return formatted time string with weekday for GUI display"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        wd = weekdays[self.current_time.weekday()]
        return f"{self.current_time.strftime('%Y-%m-%d')} {wd} {self.current_time.strftime('%H:%M')}"
