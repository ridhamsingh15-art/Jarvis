from enum import StrEnum


class PluginState(StrEnum):
    DISCOVERED = "DISCOVERED"
    LOADED = "LOADED"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"

class PluginType(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    THIRD_PARTY = "THIRD_PARTY"

class PluginCapability(StrEnum):
    TOOL = "TOOL"
    PROVIDER = "PROVIDER"
    TRANSPORT = "TRANSPORT"
    MEMORY = "MEMORY"
    EVENT_HANDLER = "EVENT_HANDLER"
    WORKFLOW = "WORKFLOW"
    SKILL = "SKILL"
