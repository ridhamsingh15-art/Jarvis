from enum import StrEnum


class PackageState(StrEnum):
    INSTALLED = "INSTALLED"
    UNINSTALLED = "UNINSTALLED"
    PENDING = "PENDING"
    FAILED = "FAILED"
    CACHED = "CACHED"

class RepositoryType(StrEnum):
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    LOCAL = "LOCAL"
    OFFLINE = "OFFLINE"

class CacheState(StrEnum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    CORRUPTED = "CORRUPTED"
