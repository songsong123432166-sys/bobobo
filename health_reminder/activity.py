class ActivityMonitor:
    def __init__(
        self,
        get_idle_seconds,
        is_media_playing,
        away_after_minutes=5,
        idle_after_minutes=15,
    ):
        self.get_idle_seconds = get_idle_seconds
        self.is_media_playing = is_media_playing
        self.away_after_minutes = away_after_minutes
        self.idle_after_minutes = idle_after_minutes
        self.state = "using"
        self.media_active = False

    def update_thresholds(self, away_after_minutes, idle_after_minutes):
        self.away_after_minutes = away_after_minutes
        self.idle_after_minutes = idle_after_minutes

    def idle_minutes(self):
        return self.get_idle_seconds() / 60

    def current_state(self):
        self.media_active = self.is_media_playing()
        if self.media_active:
            return "using"

        minutes = self.idle_minutes()
        if minutes >= self.idle_after_minutes:
            return "away"
        if minutes >= self.away_after_minutes:
            return "idle"
        return "using"

    def refresh(self):
        old_state = self.state
        self.state = self.current_state()
        return old_state, self.state

    def is_available_for_reminders(self):
        return self.state == "using"

    def label(self):
        if self.state == "away":
            return "离开"
        if self.state == "idle":
            return "可能离开"
        if self.media_active:
            return "使用中（视频/会议）"
        return "使用中"
