import enum


class TelegramAccountStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"


class AutomationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    ERROR = "ERROR"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class AutomationPriority(str, enum.Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class SelectionStrategy(str, enum.Enum):
    """Bir fieldga bir nechta action bo'lganda (Playlist preset) qaysi birini tanlash."""

    NONE = "NONE"
    SEQUENTIAL = "SEQUENTIAL"
    RANDOM = "RANDOM"
    # Har action'da at_time (HH:MM) bor; hozirgi mahalliy vaqtga mos oxirgi action tanlanadi (Jadval xizmati).
    BY_TIME = "BY_TIME"


class TriggerType(str, enum.Enum):
    INTERVAL = "INTERVAL"
    SCHEDULE = "SCHEDULE"
    WINDOW = "WINDOW"


class ProfileField(str, enum.Enum):
    NAME = "name"
    BIO = "bio"
    EMOJI_STATUS = "emoji_status"
    ONLINE = "online"
    PHOTO = "photo"
    BIRTHDAY = "birthday"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, enum.Enum):
    MANUAL_ADMIN = "MANUAL_ADMIN"
    BOT_AUTO = "BOT_AUTO"


class TransactionType(str, enum.Enum):
    TOPUP = "TOPUP"
    PURCHASE = "PURCHASE"
    REFUND = "REFUND"
    REFERRAL_BONUS = "REFERRAL_BONUS"
    ADJUSTMENT = "ADJUSTMENT"


class WorkerJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class ActorType(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"
