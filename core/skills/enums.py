from enum import StrEnum


class SkillType(StrEnum):
    BUILTIN = "BUILTIN"
    USER = "USER"
    LEARNED = "LEARNED"
    COMPOSED = "COMPOSED"

class SkillStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    EXPERIMENTAL = "EXPERIMENTAL"
    DEPRECATED = "DEPRECATED"
