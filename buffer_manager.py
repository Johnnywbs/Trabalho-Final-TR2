class BufferManager:
    def __init__(self):
        self.buffer_level_s = 0.0
        self.total_rebuffer_events = 0
        self.total_stall_duration_s = 0.0

    def update_buffer(self, download_time_s, segment_duration_s):
        rebuffer_event = 0
        stall_duration_s = 0.0

        self.buffer_level_s -= download_time_s

        if self.buffer_level_s < 0:
            rebuffer_event = 1
            stall_duration_s = abs(self.buffer_level_s)
            self.total_rebuffer_events += 1
            self.total_stall_duration_s += stall_duration_s
            self.buffer_level_s = 0.0
            buffer_can_play = 0
        else:
            buffer_can_play = 1

        self.buffer_level_s += segment_duration_s

        status = "STALLED⚠️ " if rebuffer_event else "Smooth✅"
        print(f"[Buffer] Level: {self.buffer_level_s:.2f}s | {status} "
              f"(Stall: {stall_duration_s:.2f}s)")

        return buffer_can_play, rebuffer_event, stall_duration_s

    def get_current_level(self):
        return self.buffer_level_s
