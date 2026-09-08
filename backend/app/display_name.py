"""How a teacher's name appears in greetings and the sidebar.

一律展示全名；曾经的「姓氏+老师」偏好已下线。
"""


def teacher_display_name(name: str | None) -> str:
    return (name or "").strip()
