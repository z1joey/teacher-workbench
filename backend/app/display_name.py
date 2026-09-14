"""How a teacher's name appears in greetings and the sidebar.

一律展示全名；曾经的「姓氏+老师」偏好已下线。
"""


def teacher_display_name(name: str | None, email: str | None = None) -> str:
    """姓名为空（注册未填或个人中心清空）时回退到邮箱前缀。"""
    stripped = (name or "").strip()
    if stripped:
        return stripped
    return (email or "").split("@", 1)[0].strip()
