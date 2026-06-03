"""DB ENUM 타입과 1:1 대응하는 Python Enum (migrations/*.sql 기준)."""
from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    wholesaler = "wholesaler"
    retail_seller = "retail_seller"
    agency = "agency"


class AccountStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class SellerType(str, Enum):
    agency_affiliated = "agency_affiliated"
    independent = "independent"


class ProductStatus(str, Enum):
    active = "active"
    archived = "archived"


class ImageMatch(str, Enum):
    matched = "matched"
    unmatched = "unmatched"


class UploadStatus(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    needs_matching = "needs_matching"
    completed = "completed"
    failed = "failed"


class PriceVisibility(str, Enum):
    wholesale = "wholesale"
    retail = "retail"
    none = "none"
