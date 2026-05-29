from datetime import timedelta


def build_reminder_candidates(last_sit_reset, last_water_reset, config, sit_message, water_message):
    return [
        {
            "kind": "sit",
            "title": "久坐提醒",
            "message": sit_message,
            "due_at": last_sit_reset + timedelta(minutes=config["sit_interval_minutes"]),
        },
        {
            "kind": "water",
            "title": "喝水提醒",
            "message": water_message,
            "due_at": last_water_reset + timedelta(minutes=config["water_interval_minutes"]),
        },
    ]


def collect_due_reminders(candidates, now):
    return [item for item in candidates if item["due_at"] <= now]


def merge_nearby_reminders(candidates, now, due_items, merge_window_minutes):
    merge_window = timedelta(minutes=merge_window_minutes)
    reminders = list(due_items)
    kinds = {item["kind"] for item in reminders}
    for item in candidates:
        if item["kind"] in kinds:
            continue
        if timedelta(0) < item["due_at"] - now <= merge_window:
            reminders.append(item)
            kinds.add(item["kind"])
    return reminders
