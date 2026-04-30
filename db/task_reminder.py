import json
import os

TASKS_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")


def _load():
    with open(TASKS_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_all_tasks():
    return _load()["tasks"]


def get_task_by_id(task_id):
    tasks = get_all_tasks()
    return next((t for t in tasks if t["id"] == task_id), None)


def mark_task_done(task_id):
    data = _load()
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["is_done"] = True
            _save(data)
            return task
    return None


def reset_all_tasks():
    """Reset all tasks to is_done=False. Called every Sunday for the new week."""
    data = _load()
    for task in data["tasks"]:
        task["is_done"] = False
    _save(data)
    return data["tasks"]


def get_tasks_for_shift(day, start_time):
    """Return all tasks whose shift matches the given day and start_time."""
    tasks = get_all_tasks()
    return [
        t
        for t in tasks
        if any(s["day"] == day and s["start_time"] == start_time for s in t["shifts"])
    ]


def update_task_email(task_id, email):
    data = _load()
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["email"] = email
            _save(data)
            return task
    return None
