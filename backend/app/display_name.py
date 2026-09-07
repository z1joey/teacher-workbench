"""How a teacher's name appears in greetings and the sidebar."""


def teacher_display_name(name: str | None, mode: str | None = None) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    if mode == "teacher":
        return f"{name[0]}老师"
    return name
