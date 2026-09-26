import enum


class LoginStatus(str, enum.Enum):
    WAITING_SCAN = "WAITING_SCAN"
    CODE_SENT = "CODE_SENT"
    NEED_PASSWORD = "NEED_PASSWORD"
    SUCCESS = "SUCCESS"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"
