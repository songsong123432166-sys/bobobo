from datetime import datetime


def is_now_in_clock_range(start, end, now=None):
    now_time = (now or datetime.now()).time()
    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def minutes_until(reset_at, interval_minutes, now=None):
    elapsed = ((now or datetime.now()) - reset_at).total_seconds() / 60
    return max(0, int(interval_minutes - elapsed))
