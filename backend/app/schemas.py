from pydantic import BaseModel, Field
from typing import Optional, List

class ProductBase(BaseModel):
    name: str = Field(..., example="PlayStation 5")
    brand: str = Field(..., example="Sony")
    category: Optional[str] = Field("Eletrônicos", example="Games")
    description: Optional[str] = Field("", example="Console PS5 Edição Digital")
    search_query: str = Field(..., example="PlayStation 5 Slim")
    target_price: Optional[float] = Field(None, example=3500.0)
    image_url: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(True)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    search_query: Optional[str] = None
    target_price: Optional[float] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class StoreOfferOut(BaseModel):
    store_name: str
    product_title: str
    price: float
    url: Optional[str] = None
    is_best: bool = False

class PriceRecordOut(BaseModel):
    id: int
    product_id: int
    checked_at: str
    min_price: float
    max_price: float
    avg_price: float
    best_store: str
    best_url: Optional[str] = None
    highest_store: Optional[str] = None
    recommendation: str
    recommendation_reason: Optional[str] = None
    delta_pct: float
    delta_amount: float
    offers: Optional[List[StoreOfferOut]] = []

class ProductOut(BaseModel):
    id: int
    name: str
    brand: str
    category: str
    description: Optional[str] = None
    search_query: str
    target_price: Optional[float] = None
    image_url: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str
    latest_record: Optional[PriceRecordOut] = None
    all_time_min: Optional[float] = None
    all_time_max: Optional[float] = None
    records_count: int = 0

class SearchPreviewRequest(BaseModel):
    query: str
    brand: Optional[str] = ""

class TelegramSettings(BaseModel):
    bot_token: str
    chat_id: str
    is_enabled: bool = True
    notification_hour: int = 8

class TelegramTestRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    telegram_chat_id: Optional[str] = ""

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    telegram_chat_id: Optional[str] = None
    created_at: Optional[str] = None
