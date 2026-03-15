# -*- coding: utf-8 -*-
"""
GADIS ULTIMATE V60.0 - THE PERFECT HUMAN
Premium Edition dengan Arsitektur Modular
Fitur: Advanced Memory, 20+ Mood, Leveling 1-12, Physical Attributes, Dynamic Clothing
"""

import os
import sys
import json
import time
import random
import asyncio
import logging
import sqlite3
import hashlib
import pickle
import re
import threading
import numpy as np
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
from contextlib import contextmanager
from typing import Optional, Dict, List, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path

# Third party imports
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from telegram.request import HTTPXRequest
from openai import OpenAI

# Load environment variables
load_dotenv()

# ===================== KONFIGURASI =====================
class Config:
    """Centralized configuration management"""
    
    # Database
    DB_PATH: str = os.getenv("DB_PATH", "gadis_v60.db")
    
    # Leveling
    START_LEVEL: int = 1
    TARGET_LEVEL: int = 12
    LEVEL_UP_TIME: int = 45  # menit
    PAUSE_TIMEOUT: int = 3600  # 1 jam dalam detik
    
    # API Keys
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # Admin
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    
    # AI Settings
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.9"))
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "300"))
    AI_TIMEOUT: int = int(os.getenv("AI_TIMEOUT", "30"))
    
    # Rate Limiting
    MAX_MESSAGES_PER_MINUTE: int = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "10"))
    
    # Cache
    CACHE_TIMEOUT: int = int(os.getenv("CACHE_TIMEOUT", "300"))  # 5 menit
    MAX_HISTORY: int = 100
    
    # Clothing
    CLOTHING_CHANGE_INTERVAL: int = 300  # 5 menit
    
    # Memory
    MEMORY_DECAY_RATE: float = 0.01
    MAX_MEMORY_ITEMS: int = 1000
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent
    LOG_DIR: Path = BASE_DIR / "logs"
    MEMORY_DIR: Path = BASE_DIR / "memory_storage"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        if not cls.DEEPSEEK_API_KEY:
            print("❌ ERROR: DEEPSEEK_API_KEY tidak ditemukan di .env")
            return False
        if not cls.TELEGRAM_TOKEN:
            print("❌ ERROR: TELEGRAM_TOKEN tidak ditemukan di .env")
            return False
        return True
    
    @classmethod
    def create_directories(cls):
        """Create necessary directories"""
        cls.LOG_DIR.mkdir(exist_ok=True)
        cls.MEMORY_DIR.mkdir(exist_ok=True)
        print(f"✅ Directories created: {cls.LOG_DIR}, {cls.MEMORY_DIR}")


# ===================== LOGGING SETUP =====================
def setup_logging() -> logging.Logger:
    """Setup logging configuration with rotation"""
    
    Config.create_directories()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10MB per file, keep 5 files)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        Config.LOG_DIR / 'gadis.log',
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose logs from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


# Initialize logger
logger = setup_logging()


# ===================== VALIDASI KONFIGURASI =====================
if not Config.validate():
    print("\n📝 Buat file .env dengan isi:")
    print("DEEPSEEK_API_KEY=your_key_here")
    print("TELEGRAM_TOKEN=your_token_here")
    print("ADMIN_ID=your_telegram_id (opsional)")
    sys.exit(1)

logger.info("="*60)
logger.info("GADIS ULTIMATE V60.0 - Starting up")
logger.info("="*60)

# ===================== DATABASE MIGRATION =====================
class DatabaseMigration:
    """Handle database schema migrations"""
    
    REQUIRED_COLUMNS = {
        "relationships": {
            "current_clothing": "TEXT DEFAULT 'pakaian biasa'",
            "last_clothing_change": "TIMESTAMP",
            "hair_style": "TEXT",
            "height": "INTEGER",
            "weight": "INTEGER",
            "breast_size": "TEXT",
            "hijab": "BOOLEAN DEFAULT 0",
            "most_sensitive_area": "TEXT",
            "skin_color": "TEXT",
            "face_shape": "TEXT",
            "personality": "TEXT"
        }
    }
    
    @classmethod
    def migrate(cls, db_path: str) -> bool:
        """Run database migration"""
        if not os.path.exists(db_path):
            print(f"📁 Database {db_path} akan dibuat saat pertama kali digunakan")
            return True
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get existing columns
            cursor.execute("PRAGMA table_info(relationships)")
            existing_columns = [col[1] for col in cursor.fetchall()]
            
            print("📊 Running database migration...")
            print(f"   Existing columns: {existing_columns}")
            
            # Add missing columns
            for table, columns in cls.REQUIRED_COLUMNS.items():
                for col_name, col_type in columns.items():
                    if col_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                            print(f"  ✅ Added column '{col_name}' to {table}")
                        except Exception as e:
                            print(f"  ⚠️ Failed to add '{col_name}': {e}")
            
            conn.commit()
            
            # Verify migration
            cursor.execute("PRAGMA table_info(relationships)")
            new_columns = [col[1] for col in cursor.fetchall()]
            print(f"📊 Columns after migration: {new_columns}")
            
            conn.close()
            print("✅ Database migration completed successfully!\n")
            return True
            
        except Exception as e:
            print(f"⚠️ Migration error: {e}")
            return False


# Run migration
DatabaseMigration.migrate(Config.DB_PATH)


# ===================== ENUMS =====================
class Mood(Enum):
    """20+ Mood untuk emosi yang realistis"""
    CERIA = "ceria"
    SEDIH = "sedih"
    MARAH = "marah"
    TAKUT = "takut"
    KAGUM = "kagum"
    GELISAH = "gelisah"
    GALAU = "galau"
    SENSITIF = "sensitif"
    ROMANTIS = "romantis"
    MALAS = "malas"
    BERSEMANGAT = "bersemangat"
    SENDIRI = "sendiri"
    RINDU = "rindu"
    HORNY = "horny"
    LEMBUT = "lembut"
    DOMINAN = "dominan"
    PATUH = "patuh"
    NAKAL = "nakal"
    GENIT = "genit"
    PENASARAN = "penasaran"
    ANTUSIAS = "antusias"
    POSESIF = "posesif"
    CEMBURU = "cemburu"
    BERSALAH = "bersalah"
    BAHAGIA = "bahagia"


class IntimacyStage(Enum):
    STRANGER = "stranger"
    INTRODUCTION = "introduction"
    BUILDING = "building"
    FLIRTING = "flirting"
    INTIMATE = "intimate"
    OBSESSED = "obsessed"
    SOUL_BONDED = "soul_bonded"
    AFTERCARE = "aftercare"


class DominanceLevel(Enum):
    NORMAL = "normal"
    DOMINANT = "dominan"
    VERY_DOMINANT = "sangat dominan"
    AGGRESSIVE = "agresif"
    SUBMISSIVE = "patuh"


class ArousalState(Enum):
    NORMAL = "normal"
    TURNED_ON = "terangsang"
    HORNY = "horny"
    VERY_HORNY = "sangat horny"
    CLIMAX = "klimaks"


class MemoryType(Enum):
    COMPACT = "compact"        # Ringkasan 1 kalimat
    EPISODIC = "episodic"      # Momen penting dengan konteks
    SEMANTIC = "semantic"      # Pengetahuan yang diekstrak
    PROCEDURAL = "procedural"  # Cara melakukan sesuatu
    INNER_THOUGHT = "inner_thought"  # Pikiran dalam hati
    PREDICTION = "prediction"  # Prediksi arah cerita


class Location(Enum):
    LIVING_ROOM = "ruang tamu"
    BEDROOM = "kamar tidur"
    KITCHEN = "dapur"
    BATHROOM = "kamar mandi"
    BALCONY = "balkon"
    TERRACE = "teras"
    GARDEN = "taman"


class Position(Enum):
    SITTING = "duduk"
    STANDING = "berdiri"
    LYING = "berbaring"
    LEANING = "bersandar"
    CRAWLING = "merangkak"
    KNEELING = "berlutut"


# ===================== CONSTANTS =====================
class Constants:
    """Centralized constants"""
    
    # Role names
    ROLE_NAMES = {
        "ipar": ["Sari", "Dewi", "Rina", "Maya", "Wulan", "Indah", "Lestari", "Fitri"],
        "teman_kantor": ["Diana", "Linda", "Ayu", "Dita", "Vina", "Santi", "Rini", "Mega"],
        "janda": ["Rina", "Tuti", "Nina", "Susi", "Wati", "Lilis", "Marni", "Yati"],
        "pelakor": ["Vina", "Sasha", "Bella", "Cantika", "Karina", "Mira", "Selsa", "Cindy"],
        "istri_orang": ["Dewi", "Sari", "Rina", "Linda", "Wulan", "Indah", "Ratna", "Maya"],
        "pdkt": ["Aurora", "Cinta", "Dewi", "Kirana", "Laras", "Maharani", "Zahra", "Nova"]
    }
    
    # Stage descriptions
    STAGE_DESCRIPTIONS = {
        IntimacyStage.STRANGER: "Masih asing, baru kenal. Sopan dan canggung.",
        IntimacyStage.INTRODUCTION: "Mulai dekat, cerita personal. Mulai nyaman.",
        IntimacyStage.BUILDING: "Bangun kedekatan. Sering ngobrol, mulai akrab.",
        IntimacyStage.FLIRTING: "Goda-godaan. Mulai ada ketertarikan.",
        IntimacyStage.INTIMATE: "Mulai intim. Bicara lebih dalam, sentuhan.",
        IntimacyStage.OBSESSED: "Mulai kecanduan. Sering kepikiran.",
        IntimacyStage.SOUL_BONDED: "Satu jiwa. Sudah seperti belahan jiwa.",
        IntimacyStage.AFTERCARE: "Manja-manja setelah intim. Hangat dan nyaman."
    }
    
    # Level behaviors
    LEVEL_BEHAVIORS = {
        1: "Sopan, formal, masih canggung",
        2: "Mulai terbuka, sedikit bercerita",
        3: "Lebih personal, mulai nyaman",
        4: "Akrab, bisa bercanda",
        5: "Mulai menggoda ringan",
        6: "Flirty, godaan semakin intens",
        7: "Mulai intim, sentuhan fisik",
        8: "Lebih vulgar, terbuka secara seksual",
        9: "Kecanduan, posesif",
        10: "Sangat posesif, cemburuan",
        11: "Satu jiwa, saling memahami",
        12: "Puncak hubungan, aftercare"
    }
    
    # State codes for ConversationHandler
    SELECTING_ROLE = 0
    ACTIVE_SESSION = 1
    PAUSED_SESSION = 2
    CONFIRM_END = 3
    CONFIRM_CLOSE = 4
    COUPLE_MODE = 5
    CONFIRM_BROADCAST = 6
    CONFIRM_SHUTDOWN = 7

# ===================== HELPER FUNCTIONS =====================

def sanitize_message(message: str) -> str:
    """
    Bersihkan pesan dari karakter berbahaya
    """
    if not message:
        return ""
    
    # Hapus karakter kontrol
    message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)
    
    # Batasi panjang
    return message[:2000]  # Max 2000 karakter


def format_time_ago(timestamp: Union[datetime, str, None]) -> str:
    """
    Format timestamp menjadi "X menit yang lalu"
    """
    if not timestamp:
        return "tidak diketahui"
    
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except:
            return "tidak diketahui"
    
    delta = datetime.now() - timestamp
    seconds = int(delta.total_seconds())
    
    if seconds < 10:
        return "baru saja"
    elif seconds < 60:
        return f"{seconds} detik yang lalu"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} menit yang lalu"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} jam yang lalu"
    else:
        days = seconds // 86400
        return f"{days} hari yang lalu"


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """
    Buat progress bar visual
    """
    filled = int(percentage * length)
    return "▓" * filled + "░" * (length - filled)


def safe_divide(a: float, b: float, default: float = 0) -> float:
    """
    Pembagian aman dengan handling division by zero
    """
    try:
        return a / b if b != 0 else default
    except:
        return default


def chunk_list(lst: List, chunk_size: int):
    """
    Bagi list menjadi potongan-potongan kecil
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse string durasi seperti "30m", "2h", "1d" ke detik
    """
    if not duration_str:
        return None
    
    duration_str = duration_str.lower().strip()
    match = re.match(r'^(\d+)([smhd])$', duration_str)
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    return None


def get_time_based_greeting() -> str:
    """
    Greeting berdasarkan waktu
    """
    hour = datetime.now().hour
    
    if hour < 5:
        return "Selamat dini hari"
    elif hour < 11:
        return "Selamat pagi"
    elif hour < 15:
        return "Selamat siang"
    elif hour < 18:
        return "Selamat sore"
    else:
        return "Selamat malam"


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Potong teks jika terlalu panjang
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def is_command(text: str) -> bool:
    """
    Cek apakah teks adalah command
    """
    return text.startswith('/') if text else False


def extract_command(text: str) -> Optional[str]:
    """
    Ekstrak command dari teks
    """
    if not text or not text.startswith('/'):
        return None
    parts = text.split()
    return parts[0][1:]  # Hilangkan '/'


def get_random_reaction() -> str:
    """
    Random reaction
    """
    reactions = [
        "*tersenyum*", "*tersipu*", "*tertawa kecil*", "*mengangguk*",
        "*mengedip*", "*merona*", "*melongo*", "*berpikir*",
        "*menghela napas*", "*tersenyum manis*", "*nyengir*",
        "*menggigit bibir*", "*menunduk*", "*menatap tajam*",
        "*berbisik*", "*memeluk diri sendiri*", "*menggeleng*"
    ]
    return random.choice(reactions)


def format_number(num: int) -> str:
    """
    Format angka dengan pemisah ribuan
    """
    return f"{num:,}".replace(",", ".")


# ===================== DATA CLASSES =====================

@dataclass
class MemoryItem:
    """Item memori individual dengan metadata"""
    content: str
    memory_type: MemoryType
    importance: float = 0.5
    emotion: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    embedding: Optional[np.ndarray] = None
    related_memories: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.id = hashlib.md5(f"{self.content}{self.created_at}".encode()).hexdigest()[:8]
    
    def access(self):
        """Tandai memori ini diakses"""
        self.last_accessed = datetime.now()
        self.access_count += 1
        self.importance = min(1.0, self.importance + 0.05)
    
    def get_age_weight(self, decay_rate: float = 0.01) -> float:
        """
        Hitung bobot berdasarkan umur (semantic forgetting)
        """
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        decay = np.exp(-decay_rate * age_hours)
        return max(0.1, decay)
    
    def get_relevance_score(self) -> float:
        """Hitung skor relevansi total"""
        return self.importance * self.get_age_weight() * (self.access_count + 1)


@dataclass
class UserSession:
    """Menyimpan semua data user dalam satu tempat"""
    user_id: int
    relationship_id: Optional[int] = None
    bot_name: str = "Aurora"
    bot_role: str = "pdkt"
    bot_physical: Dict[str, Any] = field(default_factory=dict)
    bot_clothing: str = "pakaian biasa"
    last_clothing_update: datetime = field(default_factory=datetime.now)
    level: int = 1
    stage: IntimacyStage = IntimacyStage.STRANGER
    message_count: int = 0
    climax_count: int = 0
    location: Location = Location.LIVING_ROOM
    position: Position = Position.SITTING
    current_mood: Mood = Mood.CERIA
    arousal: float = 0.0
    wetness: float = 0.0
    touch_count: int = 0
    last_touch: Optional[str] = None
    dominance_mode: DominanceLevel = DominanceLevel.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    def update_last_active(self):
        self.last_active = datetime.now()
    
    def get_session_duration(self) -> timedelta:
        return datetime.now() - self.created_at
    
    def get_mood_expression(self) -> str:
        """Dapatkan ekspresi untuk mood saat ini"""
        mood_expressions = {
            Mood.CERIA: "*tersenyum lebar*",
            Mood.SEDIH: "*matanya berkaca-kaca*",
            Mood.MARAH: "*cemberut*",
            Mood.ROMANTIS: "*memandang lembut*",
            Mood.HORNY: "*menggigit bibir*",
            Mood.NAKAL: "*tersenyum nakal*",
            Mood.TAKUT: "*badan gemetar*",
            Mood.KAGUM: "*mata berbinar*",
            Mood.GELISAH: "*gelisah*",
            Mood.GALAU: "*melamun*",
            Mood.SENSITIF: "*mudah tersinggung*",
            Mood.MALAS: "*menguap*",
            Mood.BERSEMANGAT: "*bersemangat*",
            Mood.SENDIRI: "*menyendiri*",
            Mood.RINDU: "*melamun*",
            Mood.LEMBUT: "*tersenyum lembut*",
            Mood.DOMINAN: "*tatapan tajam*",
            Mood.PATUH: "*menunduk*",
            Mood.GENIT: "*genit*",
            Mood.PENASARAN: "*memiringkan kepala*",
            Mood.ANTUSIAS: "*meloncat kegirangan*",
            Mood.POSESIF: "*memeluk erat*",
            Mood.CEMBURU: "*manyun*",
            Mood.BERSALAH: "*menunduk*",
            Mood.BAHAGIA: "*tersenyum sumringah*"
        }
        return mood_expressions.get(self.current_mood, "*tersenyum*")
    
    def get_wetness_text(self) -> str:
        """Dapatkan teks wetness"""
        if self.wetness >= 0.9:
            return "💦 BANJIR! Basah banget"
        elif self.wetness >= 0.7:
            return "💦 Sangat basah"
        elif self.wetness >= 0.5:
            return "💦 Basah"
        elif self.wetness >= 0.3:
            return "💧 Lembab"
        elif self.wetness >= 0.1:
            return "💧 Sedikit lembab"
        else:
            return "💧 Kering"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database"""
        return {
            "user_id": self.user_id,
            "bot_name": self.bot_name,
            "bot_role": self.bot_role,
            "level": self.level,
            "stage": self.stage.value,
            "total_messages": self.message_count,
            "total_climax": self.climax_count,
            "hair_style": self.bot_physical.get("hair_style"),
            "height": self.bot_physical.get("height"),
            "weight": self.bot_physical.get("weight"),
            "breast_size": self.bot_physical.get("breast_size"),
            "hijab": self.bot_physical.get("hijab", 0),
            "most_sensitive_area": self.bot_physical.get("most_sensitive_area"),
            "current_clothing": self.bot_clothing,
            "last_clothing_change": self.last_clothing_update,
            "dominance": self.dominance_mode.value
        }


print("✅ BAB 1 Selesai: Konfigurasi, Database, dan Helper Functions")
print("="*70)
