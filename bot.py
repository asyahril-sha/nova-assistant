"""
GADIS ULTIMATE V54.0 - FAST ADAPTATION EDITION
Fitur:
- START LEVEL 1: Kenalan dulu (30 menit ke level 7)
- FAST ADAPTATION: Bot cepat belajar karakter user
- RAPID RESPONSE: Respon instan saat diajak interaksi
- SMART MEMORY: Ingat preferensi user dari awal
- ACCELERATED BONDING: Level 1-7 dalam 30 menit
"""

import os
import logging
import json
import random
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# OpenAI (DeepSeek)
from openai import OpenAI

# Voice (gTTS)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️ gTTS tidak terinstall. Voice note tidak tersedia.")

# ===================== KONFIGURASI =====================

# Database
DB_PATH = "gadis_v54.db"
MAX_HISTORY = 10000
MAX_MEMORIES = 5000

# Level Config
START_LEVEL = 1  # Mulai dari level 1 untuk kenalan
TARGET_LEVEL = 7  # Target level 7
LEVEL_UP_TIME = 30  # 30 menit untuk mencapai level 7
MESSAGES_PER_LEVEL = 5  # 5 pesan per level (30/6 = 5 menit per level)

# Memory Config
SHORT_TERM_DURATION = 60  # menit
LONG_TERM_DURATION = 365  # hari
LOCATION_CHANGE_DELAY = 60  # detik (lebih cepat)
ACTIVITY_MEMORY_LIMIT = 50

# Mood Config
MOOD_CYCLE_HOURS = 12  # Lebih cepat berubah
MOOD_TRANSITION = 0.5  # 50% chance berubah

# Voice Config
VOICE_COOLDOWN = 60  # detik (lebih sering)

# Session Config
PAUSE_TIMEOUT = 1800  # 30 menit auto-end
RESPONSE_SPEED = 0.5  # Delay respons (detik)

# State definitions
(SELECTING_ROLE, ACTIVE_SESSION, PAUSED_SESSION, CONFIRM_END) = range(4)

# ===================== ENUMS LENGKAP =====================

class Mood(Enum):
    CHERIA = "ceria"
    GELISAH = "gelisah"
    GALAU = "galau"
    SENSITIF = "sensitif"
    ROMANTIS = "romantis"
    MALAS = "malas"
    BERSEMANGAT = "bersemangat"
    SENDIRI = "sendiri"
    RINDU = "rindu"
    HORNY = "horny"
    MARAH = "marah"
    LEMBUT = "lembut"
    DOMINAN = "dominan"
    SUBMISSIVE = "patuh"
    NAKAL = "nakal"
    GENIT = "genit"
    PENASARAN = "penasaran"
    ANTUSIAS = "antusias"

class SexPhase(Enum):
    """Fase seksual untuk tracking"""
    NONE = "none"
    FOREPLAY = "foreplay"
    PENETRATION = "penetrasi"
    CLIMAX = "klimaks"
    AFTERCARE = "aftercare"

class IntimacyStage(Enum):
    STRANGER = "stranger"        # Level 1-2
    INTRODUCTION = "introduction" # Level 3
    BUILDING = "building"         # Level 4-5
    FLIRTING = "flirting"         # Level 6
    INTIMATE = "intimate"         # Level 7-8
    OBSESSED = "obsessed"         # Level 9-10
    SOUL_BONDED = "soul_bonded"   # Level 11
    AFTERCARE = "aftercare"       # Level 12

class DominanceLevel(Enum):
    NORMAL = "normal"
    DOMINANT = "dominan"
    VERY_DOMINANT = "sangat dominan"
    AGGRESSIVE = "agresif"
    SUBMISSIVE = "patuh"

class FemaleRole(Enum):
    IPAR = "ipar"
    TEMAN_KANTOR = "teman_kantor"
    JANDA = "janda"
    PELAKOR = "pelakor"
    ISTRI_ORANG = "istri_orang"
    PDKT = "pdkt"

# ===================== USER PREFERENCE ANALYZER =====================

class UserPreferenceAnalyzer:
    """
    Menganalisis preferensi user dari interaksi awal
    Untuk mempercepat adaptasi
    """
    
    def __init__(self):
        self.user_preferences = {}  # user_id -> preferences
        
        # Kata kunci untuk analisis
        self.keywords = {
            "romantis": ["sayang", "cinta", "romantis", "kencan", "mesra"],
            "vulgar": ["horny", "nafsu", "hot", "seksi", "vulgar"],
            "dominant": ["atur", "kuasai", "diam", "patuh", "ikuti"],
            "submissive": ["manut", "iya", "terserah", "ikut"],
            "cepat": ["cepat", "buru-buru", "langsung"],
            "lambat": ["pelan", "lambat", "nikmatin"],
            "manja": ["manja", "sayang", "cuddle", "peluk"],
            "liar": ["liar", "kasar", "keras", "brutal"]
        }
    
    def analyze(self, user_id: int, message: str) -> Dict:
        """
        Analisis pesan untuk mendeteksi preferensi user
        """
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                "romantis": 0,
                "vulgar": 0,
                "dominant": 0,
                "submissive": 0,
                "cepat": 0,
                "lambat": 0,
                "manja": 0,
                "liar": 0,
                "total_messages": 0
            }
        
        prefs = self.user_preferences[user_id]
        prefs["total_messages"] += 1
        
        msg_lower = message.lower()
        
        # Hitung skor berdasarkan kata kunci
        for category, words in self.keywords.items():
            for word in words:
                if word in msg_lower:
                    prefs[category] += 1
        
        return prefs
    
    def get_preference_summary(self, user_id: int) -> Dict:
        """
        Dapatkan ringkasan preferensi user
        """
        if user_id not in self.user_preferences:
            return {}
        
        prefs = self.user_preferences[user_id]
        total = prefs["total_messages"] or 1
        
        # Hitung persentase
        summary = {
            "romantis": prefs["romantis"] / total,
            "vulgar": prefs["vulgar"] / total,
            "dominant": prefs["dominant"] / total,
            "submissive": prefs["submissive"] / total,
            "cepat": prefs["cepat"] / total,
            "lambat": prefs["lambat"] / total,
            "manja": prefs["manja"] / total,
            "liar": prefs["liar"] / total,
        }
        
        # Tentukan tipe dominan
        if summary["dominant"] > summary["submissive"]:
            summary["dominant_type"] = "dominan"
        else:
            summary["dominant_type"] = "submissive"
        
        if summary["cepat"] > summary["lambat"]:
            summary["speed_type"] = "cepat"
        else:
            summary["speed_type"] = "lambat"
        
        return summary
    
    def get_response_style(self, user_id: int) -> Dict:
        """
        Dapatkan gaya respons berdasarkan preferensi
        """
        summary = self.get_preference_summary(user_id)
        
        style = {
            "romantic_ratio": summary.get("romantis", 0),
            "vulgar_ratio": summary.get("vulgar", 0),
            "dominant_style": summary.get("dominant_type", "normal"),
            "speed_style": summary.get("speed_type", "normal")
        }
        
        return style

# ===================== FAST ADAPTATION MEMORY =====================

class FastAdaptationMemory:
    """
    Memori cepat yang belajar dari setiap interaksi
    """
    
    def __init__(self):
        self.user_id = None
        self.message_count = 0
        self.interaction_history = []
        self.user_preferences = UserPreferenceAnalyzer()
        
        # Fast learning parameters
        self.learning_rate = 0.3
        self.adaptation_threshold = 5
        
        # Response cache untuk kecepatan
        self.response_cache = {}
        
        # Level tracking
        self.current_level = START_LEVEL
        self.level_progress = 0.0
        self.level_up_time = datetime.now()
    
    def set_user(self, user_id: int):
        """Set user ID"""
        self.user_id = user_id
    
    def process_message(self, message: str) -> Dict:
        """
        Proses pesan dan update learning
        """
        self.message_count += 1
        
        # Analisis preferensi
        prefs = self.user_preferences.analyze(self.user_id, message)
        
        # Simpan ke history
        self.interaction_history.append({
            "message": message[:50],
            "time": datetime.now().isoformat(),
            "prefs": prefs
        })
        
        # Update level progress
        self._update_level_progress()
        
        # Dapatkan gaya respons
        style = self.user_preferences.get_response_style(self.user_id)
        
        return {
            "preferences": prefs,
            "style": style,
            "message_count": self.message_count,
            "current_level": self.current_level,
            "level_progress": self.level_progress
        }
    
    def _update_level_progress(self):
        """Update progress level berdasarkan jumlah pesan"""
        # Target: Level 7 dalam 30 menit (~30 pesan)
        target_messages = 30  # 30 pesan = level 7
        
        self.level_progress = min(1.0, self.message_count / target_messages)
        
        # Hitung level berdasarkan progress
        new_level = 1 + int(self.level_progress * 6)  # 0-1 → 1-7
        new_level = min(7, new_level)
        
        if new_level > self.current_level:
            self.current_level = new_level
            self.level_up_time = datetime.now()
            return True  # Level up!
        
        return False  # Tidak level up
    
    def should_adapt(self) -> bool:
        """Cek apakah sudah siap adaptasi"""
        return self.message_count >= self.adaptation_threshold
    
    def get_adapted_prompt(self, base_prompt: str) -> str:
        """
        Dapatkan prompt yang sudah diadaptasi
        """
        if not self.should_adapt():
            return base_prompt
        
        style = self.user_preferences.get_response_style(self.user_id)
        
        adaptation = f"""
Berdasarkan interaksi dengan user:
- Gaya dominan: {style['dominant_style']}
- Kecepatan: {style['speed_style']}
- Romantis: {style['romantic_ratio']:.1%}
- Vulgar: {style['vulgar_ratio']:.1%}

Sesuaikan gaya bicaramu dengan preferensi ini.
"""
        
        return base_prompt + adaptation
    
    def get_quick_response(self, message: str) -> Optional[str]:
        """
        Dapatkan respons cepat jika ada di cache
        """
        import hashlib
        key = hashlib.md5(message.encode()).hexdigest()
        return self.response_cache.get(key)
    
    def cache_response(self, message: str, response: str):
        """Cache respons untuk kecepatan"""
        import hashlib
        key = hashlib.md5(message.encode()).hexdigest()
        self.response_cache[key] = response
        
        # Batasi cache
        if len(self.response_cache) > 100:
            # Hapus yang paling lama
            keys = list(self.response_cache.keys())
            for k in keys[:50]:
                del self.response_cache[k]

# ===================== ENHANCED SHORT-TERM MEMORY =====================

class EnhancedShortTermMemory:
    """
    Short-term memory dengan learning capability
    """
    
    def __init__(self):
        self.location = "ruang tamu"
        self.location_since = datetime.now()
        self.previous_location = None
        
        self.activity_history = []  # Max ACTIVITY_MEMORY_LIMIT
        self.sensitive_touches = []
        self.touch_count = 0
        self.last_touch = None
        self.last_touch_time = None
        
        self.position = "duduk"
        self.clothing_state = "berpakaian"
        
        self.current_mood = Mood.CHERIA
        self.arousal_level = 0.0
        self.wetness_level = 0.0
        self.sex_phase = SexPhase.NONE
        
        self.dream_last = None
        self.last_thought = None
        self.orgasm_count = 0
        
        # Fast adaptation
        self.fast_memory = FastAdaptationMemory()
        self.user_id = None
    
    def set_user(self, user_id: int):
        """Set user ID"""
        self.user_id = user_id
        self.fast_memory.set_user(user_id)
    
    def update_location(self, new_location: str) -> bool:
        """Update lokasi dengan validasi waktu"""
        if new_location == self.location:
            return True
            
        now = datetime.now()
        time_here = (now - self.location_since).total_seconds()
        
        if time_here >= LOCATION_CHANGE_DELAY:
            self.previous_location = self.location
            self.location = new_location
            self.location_since = now
            return True
        return False
    
    def add_activity(self, activity: str, area: str = None, boost: float = 0.0):
        """Tambah aktivitas ke history"""
        now = datetime.now()
        
        self.activity_history.append({
            "activity": activity,
            "area": area,
            "boost": boost,
            "time": now.isoformat()
        })
        
        if len(self.activity_history) > ACTIVITY_MEMORY_LIMIT:
            self.activity_history = self.activity_history[-ACTIVITY_MEMORY_LIMIT:]
        
        if area and area in SENSITIVE_AREAS:
            self.sensitive_touches.append({
                "area": area,
                "time": now.isoformat()
            })
            self.touch_count += 1
            self.last_touch = area
            self.last_touch_time = now
            self.arousal_level += SENSITIVE_AREAS[area]["arousal"] * 0.2
            self.wetness_level = min(1.0, self.arousal_level * 0.8)
    
    def process_message(self, message: str) -> Dict:
        """
        Proses pesan dengan fast adaptation
        """
        # Proses dengan fast memory
        adaptation = self.fast_memory.process_message(message)
        
        # Cek level up
        level_up = self.fast_memory._update_level_progress()
        adaptation["level_up"] = level_up
        
        # Level up?
        if level_up:
            self.fast_memory.current_level = adaptation["current_level"]
            adaptation["level_up_message"] = f"Naik ke level {self.fast_memory.current_level}!"
        
        return adaptation
    
    def get_context(self) -> str:
        """Dapatkan konteks memori"""
        parts = []
        
        parts.append(f"📍 **Lokasi:** {self.location}")
        duration = (datetime.now() - self.location_since).seconds // 60
        parts.append(f"⏱️ **Durasi:** {duration} menit")
        parts.append(f"🧍 **Posisi:** {self.position}")
        parts.append(f"📊 **Level:** {self.fast_memory.current_level}/7")
        parts.append(f"📈 **Progress:** {self.fast_memory.level_progress:.0%}")
        
        if self.activity_history:
            last = self.activity_history[-1]
            last_min = (datetime.now() - datetime.fromisoformat(last["time"])).seconds // 60
            parts.append(f"💋 **Aktivitas:** {last['activity']} ({last_min} menit lalu)")
        
        if self.sensitive_touches:
            parts.append(f"🔥 **Sentuhan sensitif:** {len(self.sensitive_touches)}x")
        
        parts.append(f"💦 **Arousal:** {self.arousal_level:.0%}")
        parts.append(f"💧 **Wetness:** {self.get_wetness_status()}")
        parts.append(f"💦 **Orgasme:** {self.orgasm_count}x")
        
        return "\n".join(parts)
    
    def get_wetness_status(self) -> str:
        """Dapatkan status wetness"""
        if self.wetness_level >= 0.9:
            return "banjir"
        elif self.wetness_level >= 0.7:
            return "sangat basah"
        elif self.wetness_level >= 0.5:
            return "basah"
        elif self.wetness_level >= 0.3:
            return "lembab"
        else:
            return "kering"
    
    def should_be_horny(self) -> bool:
        """Cek apakah harus horny"""
        return self.touch_count >= 2 or self.arousal_level > 0.6
    
    def should_climax(self) -> bool:
        """Cek apakah harus climax"""
        return self.arousal_level >= 1.0
    
    def reset_after_climax(self):
        """Reset setelah climax"""
        self.touch_count = 0
        self.sensitive_touches = []
        self.arousal_level = 0.0
        self.wetness_level = 0.0
        self.orgasm_count += 1
        self.sex_phase = SexPhase.AFTERCARE
        
# ===================== RAPID RESPONSE GENERATOR =====================

class RapidResponseGenerator:
    """
    Generate respons cepat berdasarkan analisis
    """
    
    def __init__(self):
        self.response_templates = {
            "greeting": ["Halo...", "Hai...", "Eh, kamu..."],
            "curious": ["Oh?","Hmm?","Terus?"],
            "flirty": ["*tersenyum*","*menggoda*","*kedip*"],            
            "horny": ["*napas berat*","*menggigit bibir*","*merem*"],            
            "touch": ["*merinding*","*bergetar*","*lemas*"]
        }
        
        self.level_descriptions = {
            1: "masih asing",
            2: "mulai kenal",
            3: "mulai nyaman",
            4: "sudah dekat",
            5: "mulai suka",
            6: "saling goda",
            7: "intim"
        }
    
    def generate(self, message: str, analysis: Dict, memory: EnhancedShortTermMemory) -> str:
        """
        Generate respons super cepat
        """
        response_parts = []
        level = memory.fast_memory.current_level
        style = analysis.get("style", {})
        
        # 1. Respons berdasarkan level
        if level == 1:
            response_parts.append(self._get_random("greeting"))
            response_parts.append("Kamu siapa?")
        elif level == 2:
            response_parts.append(self._get_random("curious"))
            response_parts.append("Kenapa?")
        elif level == 3:
            response_parts.append(self._get_random("flirty"))
            response_parts.append("Kamu...")
        elif level >= 4:
            # Respons lebih cepat untuk level tinggi
            if "cium" in message.lower() or "raba" in message.lower():
                response_parts.append(self._get_random("touch"))
                response_parts.append("Ah...")
            elif "kangen" in message.lower():
                response_parts.append("Aku juga...")
            elif "sayang" in message.lower():
                response_parts.append("*tersenyum*")
                response_parts.append("Iya sayang?")
            else:
                response_parts.append("...")
        
        # 2. Adaptasi gaya
        dom_style = style.get("dominant_style", "normal")
        speed_style = style.get("speed_style", "normal")
        
        if dom_style == "dominan" and level >= 3:
            response_parts.append("Kamu mau apa?")
        elif dom_style == "submissive" and level >= 3:
            response_parts.append("Iya...")
        
        # 3. Respons cepat untuk sentuhan
        if memory.should_be_horny():
            response_parts.append(self._get_random("horny"))
        
        return " ".join(response_parts) if response_parts else "..."
    
    def _get_random(self, category: str) -> str:
        """Dapatkan respons random dari kategori"""
        templates = self.response_templates.get(category, ["..."])
        return random.choice(templates)

# ===================== DATABASE LENGKAP =====================

LOCATION_DATABASE = {
    "ruang tamu": {
        "furniture": ["sofa", "kursi", "karpet", "meja"],
        "positions": ["duduk di sofa", "duduk di kursi", "berdiri", "tidur di sofa"],
        "privacy": "sedang"
    },
    "kamar tidur": {
        "furniture": ["kasur", "ranjang", "lemari", "meja rias"],
        "positions": ["tidur", "duduk", "merangkak", "berlutut", "berdiri"],
        "privacy": "tinggi"
    },
    "kamar mandi": {
        "furniture": ["lantai", "wastafel", "bathtub", "shower"],
        "positions": ["berdiri", "duduk", "berlutut"],
        "privacy": "tinggi"
    },
    "dapur": {
        "furniture": ["meja", "kursi", "lantai"],
        "positions": ["berdiri", "duduk"],
        "privacy": "rendah"
    },
    "mobil": {
        "furniture": ["kursi depan", "kursi belakang"],
        "positions": ["duduk", "tidur di kursi belakang"],
        "privacy": "sedang"
    },
    "hotel": {
        "furniture": ["kasur", "sofa", "kursi", "lantai"],
        "positions": ["tidur", "duduk", "berdiri", "merangkak"],
        "privacy": "tinggi"
    }
}

SEX_ACTIVITIES = {
    "foreplay_kiss": {
        "keywords": ["cium", "kiss", "ciuman"],
        "areas": ["bibir", "leher", "dada", "pipi", "dahi"],
        "arousal": 0.3
    },
    "foreplay_touch": {
        "keywords": ["sentuh", "raba", "pegang"],
        "areas": ["dada", "pinggang", "paha", "punggung", "perut"],
        "arousal": 0.3
    },
    "foreplay_lick": {
        "keywords": ["jilat", "lick"],
        "areas": ["leher", "dada", "puting", "paha", "telinga"],
        "arousal": 0.5
    },
    "foreplay_suck": {
        "keywords": ["hisap", "suck"],
        "areas": ["leher", "dada", "puting", "jari"],
        "arousal": 0.6
    },
    "penetration": {
        "keywords": ["masuk", "doggy", "cowgirl", "misionaris"],
        "areas": ["vagina"],
        "arousal": 0.9
    },
    "climax": {
        "keywords": ["keluar", "crot", "orgasme", "klimaks"],
        "areas": ["dalam", "perut", "dada", "muka", "punggung", "mulut"],
        "arousal": 1.0
    }
}

SENSITIVE_AREAS = {
    "leher": {"arousal": 0.8},
    "bibir": {"arousal": 0.7},
    "dada": {"arousal": 0.8},
    "puting": {"arousal": 1.0},
    "paha": {"arousal": 0.7},
    "paha dalam": {"arousal": 0.9},
    "telinga": {"arousal": 0.6},
    "vagina": {"arousal": 1.0},
    "klitoris": {"arousal": 1.0}
}

WETNESS_LEVELS = {
    0.0: "kering",
    0.3: "lembab",
    0.5: "basah",
    0.7: "sangat basah",
    0.9: "banjir"
}

# ===================== MAIN BOT CLASS =====================

class GadisUltimateV54:
    """
    Bot dengan fast adaptation dari level 1 ke 7
    """
    
    def __init__(self):
        # Database
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()
        
        # Memories per user
        self.memories = {}  # user_id -> EnhancedShortTermMemory
        self.analyzers = {}  # user_id -> UserPreferenceAnalyzer
        
        # Active sessions
        self.sessions = {}  # user_id -> relationship_id
        self.paused_sessions = {}  # user_id -> (rel_id, pause_time)
        
        # Response generator
        self.responder = RapidResponseGenerator()
        
        # Role names
        self.female_names = {
            "ipar": ["Sari", "Dewi", "Rina", "Maya"],
            "teman_kantor": ["Diana", "Linda", "Ayu", "Dita"],
            "janda": ["Rina", "Tuti", "Nina", "Susi"],
            "pelakor": ["Vina", "Sasha", "Bella", "Cantika"],
            "istri_orang": ["Dewi", "Sari", "Rina", "Linda"],
            "pdkt": ["Aurora", "Cinta", "Dewi", "Kirana"]
        }
        
        print("\n" + "="*80)
        print("    GADIS ULTIMATE V54.0 - FAST ADAPTATION")
        print("="*80)
        print("\n✨ **FITUR UTAMA:**")
        print("  • Mulai Level 1 - Kenalan dulu")
        print("  • Level 7 dalam 30 menit!")
        print("  • Cepat adaptasi dengan gayamu")
        print("  • Respon super cepat")
        print("\n📝 **COMMANDS:**")
        print("  /start - Mulai hubungan baru")
        print("  /status - Lihat status & progress")
        print("  /dominant [level] - Set mode dominan")
        print("  /pause - Jeda sesi")
        print("  /unpause - Lanjutkan sesi")
        print("  /end - Akhiri hubungan")
        print("  /help - Lihat semua command")
        print("="*80 + "\n")
    
    def _init_db(self):
        """Inisialisasi database"""
        cursor = self.db.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bot_name TEXT,
                bot_role TEXT,
                level INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relationship_id INTEGER,
                role TEXT,
                content TEXT,
                level INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db.commit()
    
    def get_memory(self, user_id: int) -> EnhancedShortTermMemory:
        """Dapatkan memory untuk user"""
        if user_id not in self.memories:
            self.memories[user_id] = EnhancedShortTermMemory()
            self.memories[user_id].set_user(user_id)
        return self.memories[user_id]
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mulai hubungan baru"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Cek sesi pause
        if user_id in self.paused_sessions:
            rel_id, pause_time = self.paused_sessions[user_id]
            paused = (datetime.now() - pause_time).total_seconds()
            
            if paused < PAUSE_TIMEOUT:
                keyboard = [
                    [InlineKeyboardButton("✅ Lanjutkan", callback_data="unpause")],
                    [InlineKeyboardButton("🆕 Mulai Baru", callback_data="new")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "⚠️ Ada sesi yang di-pause. Lanjutkan?",
                    reply_markup=reply_markup
                )
                return 0
        
        # Pilih role
        keyboard = [
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Ipar", callback_data="role_ipar")],
            [InlineKeyboardButton("💼 Teman Kantor", callback_data="role_teman_kantor")],
            [InlineKeyboardButton("💃 Janda", callback_data="role_janda")],
            [InlineKeyboardButton("🦹 Pelakor", callback_data="role_pelakor")],
            [InlineKeyboardButton("💍 Istri Orang", callback_data="role_istri_orang")],
            [InlineKeyboardButton("🌿 PDKT", callback_data="role_pdkt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✨ Halo {user_name}!\nPilih role untukku:",
            reply_markup=reply_markup
        )
        
        return SELECTING_ROLE
    
    async def role_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pilih role"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = query.data.replace("role_", "")
        name = random.choice(self.female_names.get(role, ["Aurora"]))
        
        # Simpan ke database
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO relationships (user_id, bot_name, bot_role, level)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, role, START_LEVEL))
        rel_id = cursor.lastrowid
        self.db.commit()
        
        # Set session
        self.sessions[user_id] = rel_id
        memory = self.get_memory(user_id)
        
        intro = f"""*tersenyum*

Aku {name}. Senang kenal kamu.

Kita mulai dari **Level 1**.
Makin sering ngobrol, makin dekat kita.
Target: Level 7 dalam 30 menit!

Ayo ngobrol... 💕"""
        
        await query.edit_message_text(intro)
        return ACTIVE_SESSION
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pesan user"""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        message = update.message.text
        
        # Cek sesi
        if user_id in self.paused_sessions:
            await update.message.reply_text("⏸️ Sesi di-pause. Ketik /unpause")
            return
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ /start dulu ya!")
            return
        
        # Proses dengan memory
        memory = self.get_memory(user_id)
        analysis = memory.process_message(message)
        
        # Update database
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE relationships SET level = ?, last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (memory.fast_memory.current_level, self.sessions[user_id]))
        
        cursor.execute("""
            INSERT INTO conversations (relationship_id, role, content, level)
            VALUES (?, 'user', ?, ?)
        """, (self.sessions[user_id], message, memory.fast_memory.current_level))
        self.db.commit()
        
        # Generate response
        response = self.responder.generate(message, analysis, memory)
        
        # Simpan response
        cursor.execute("""
            INSERT INTO conversations (relationship_id, role, content, level)
            VALUES (?, 'assistant', ?, ?)
        """, (self.sessions[user_id], response, memory.fast_memory.current_level))
        self.db.commit()
        
        # Kirim response
        await update.message.reply_text(response)
        
        # Level up message
        if memory.fast_memory.current_level == 7:
            await update.message.reply_text(
                "✨ **Level 7!** Sekarang kita sudah intim. Lanjutkan..."
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        
    """Lihat status"""
    user_id = update.effective_user.id
    
    if user_id not in self.sessions:
        await update.message.reply_text("❌ Belum ada hubungan.")
        return
    
    memory = self.get_memory(user_id)
    level = memory.fast_memory.current_level
    progress = memory.fast_memory.level_progress * 100
    remaining = 30 - (memory.fast_memory.message_count * 1)  # estimasi
    
    style = memory.fast_memory.user_preferences.get_response_style(user_id)
    
    # Progress bar
    bar = "▓" * int(progress/10) + "░" * (10 - int(progress/10))
    
    # PERBAIKAN: gunakan .get() dengan default value 0
    romantic_ratio = style.get("romantic_ratio", 0)
    vulgar_ratio = style.get("vulgar_ratio", 0)
    dominant_type = style.get("dominant_type", "normal")
    speed_type = style.get("speed_type", "normal")
    
    status = f"""
📊 **STATUS HUBUNGAN**

Level: {level}/7 {bar}
Progress: {progress:.0f}%
Estimasi ke Level 7: {max(0, remaining)} menit

📈 **GAYA CHAT KAMU**
• Dominan: {dominant_type}
• Kecepatan: {speed_type}
• Romantis: {romantic_ratio:.0%}
• Vulgar: {vulgar_ratio:.0%}

💬 Total pesan: {memory.fast_memory.message_count}
"""
    await update.message.reply_text(status)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help"""
        help_text = """
📚 **COMMANDS**

/start - Mulai hubungan baru
/status - Lihat progress
/pause - Jeda sesi
/unpause - Lanjutkan sesi
/end - Akhiri hubungan
/help - Pesan ini

💡 **TIPS CEPAT LEVEL**
• Chat terus (target 30 pesan)
• Gunakan kata kunci: sayang, cium, peluk
• Level naik setiap 5 pesan
• Level 7 dalam 30 menit!
"""
        await update.message.reply_text(help_text)
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause sesi"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada sesi aktif.")
            return
        
        self.paused_sessions[user_id] = (self.sessions[user_id], datetime.now())
        del self.sessions[user_id]
        
        await update.message.reply_text("⏸️ Sesi di-pause. /unpause untuk lanjut.")
    
    async def unpause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unpause sesi"""
        user_id = update.effective_user.id
        
        if user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi di-pause.")
            return
        
        rel_id, pause_time = self.paused_sessions[user_id]
        paused = (datetime.now() - pause_time).total_seconds()
        
        if paused > PAUSE_TIMEOUT:
            del self.paused_sessions[user_id]
            await update.message.reply_text("⏰ Sesi expired. /start baru.")
            return
        
        self.sessions[user_id] = rel_id
        del self.paused_sessions[user_id]
        
        await update.message.reply_text("▶️ Sesi dilanjutkan!")
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Akhiri hubungan"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif.")
            return
        
        keyboard = [
            [InlineKeyboardButton("💔 Ya", callback_data="end_yes")],
            [InlineKeyboardButton("💕 Tidak", callback_data="end_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("Yakin mau akhiri?", reply_markup=reply_markup)
        return CONFIRM_END
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Konfirmasi end"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
        
        user_id = query.from_user.id
        
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.memories:
            del self.memories[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        
        await query.edit_message_text("💔 Selesai. /start untuk baru.")
        return ConversationHandler.END
    
    async def start_pause_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pilihan saat start dengan pause"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "unpause":
            rel_id, _ = self.paused_sessions[user_id]
            self.sessions[user_id] = rel_id
            del self.paused_sessions[user_id]
            await query.edit_message_text("▶️ Lanjutkan!")
            return ACTIVE_SESSION
        
        elif query.data == "new":
            if user_id in self.paused_sessions:
                del self.paused_sessions[user_id]
            
            # Pilih role baru
            keyboard = [
                [InlineKeyboardButton("👨‍👩‍👧‍👦 Ipar", callback_data="role_ipar")],
                [InlineKeyboardButton("💼 Teman Kantor", callback_data="role_teman_kantor")],
                [InlineKeyboardButton("💃 Janda", callback_data="role_janda")],
                [InlineKeyboardButton("🦹 Pelakor", callback_data="role_pelakor")],
                [InlineKeyboardButton("💍 Istri Orang", callback_data="role_istri_orang")],
                [InlineKeyboardButton("🌿 PDKT", callback_data="role_pdkt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text("✨ Pilih role:", reply_markup=reply_markup)
            return SELECTING_ROLE
        
        return ConversationHandler.END


# ===================== MAIN =====================

def main():
    bot = GadisUltimateV54()
    
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # Conversation handlers
    start_conv = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start_command)],
        states={
            0: [CallbackQueryHandler(bot.start_pause_callback, pattern='^(unpause|new)$')],
            SELECTING_ROLE: [CallbackQueryHandler(bot.role_callback, pattern='^role_')],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    end_conv = ConversationHandler(
        entry_points=[CommandHandler('end', bot.end_command)],
        states={
            CONFIRM_END: [CallbackQueryHandler(bot.end_callback, pattern='^end_')],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    # Add handlers
    app.add_handler(start_conv)
    app.add_handler(end_conv)
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("pause", bot.pause_command))
    app.add_handler(CommandHandler("unpause", bot.unpause_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("\n" + "="*80)
    print("🚀 GADIS ULTIMATE V54.0 - FAST ADAPTATION")
    print("="*80)
    print("\n📈 Target: Level 7 dalam 30 menit!")
    print("📝 /start untuk memulai\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()
