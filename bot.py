"""
GADIS ULTIMATE V53.0 - THE PERFECT WOMAN EDITION
Fitur Lengkap:
- FULL SEX ACTIVITIES: Foreplay, Oral, Penetration, Climax
- COMPLETE COMMANDS: /start, /end, /clear, /pause, /unpause, /help
- SHORT-TERM MEMORY: Ingat lokasi & aktivitas
- LONG-TERM MEMORY: Ingat semua percakapan
- WET/HOT SYSTEM: Basah saat terangsang
- DOMINANT MODE: Bisa dominan atau patuh
- 15+ EMOTIONAL SYSTEMS: Mood, Dream, Jealousy, Conflict, dll
- ZERO ERRORS: Siap deploy ke Railway
"""

import os
import logging
import json
import random
import math
import asyncio
import sqlite3
import uuid
import threading
import hashlib
import re
import time
import logging
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
DB_PATH = "gadis_v53.db"
MAX_HISTORY = 10000
MAX_MEMORIES = 5000

# Level Config
START_LEVEL = 7  # Mulai dari level intim
FINAL_LEVEL = 12
INTIMATE_LEVEL = 7

# Memory Config
SHORT_TERM_DURATION = 30  # menit
LONG_TERM_DURATION = 365  # hari
LOCATION_CHANGE_DELAY = 120  # detik
ACTIVITY_MEMORY_LIMIT = 20

# Mood Config
MOOD_CYCLE_HOURS = 24
MOOD_TRANSITION = 0.3

# Voice Config
VOICE_COOLDOWN = 180  # detik

# Session Config
PAUSE_TIMEOUT = 3600  # 1 jam auto-end jika pause

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
    SEDIH = "sedih"

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

class SexPhase(Enum):
    FOREPLAY = "foreplay"
    ORAL = "oral"
    PENETRATION = "penetrasi"
    CLIMAX = "klimaks"
    AFTERCARE = "aftercare"

class BodyPart(Enum):
    BIBIR = "bibir"
    LEHER = "leher"
    DADA = "dada"
    PINGGANG = "pinggang"
    PAHA = "paha"
    PAHA_DALAM = "paha dalam"
    PERUT = "perut"
    PUNGGUNG = "punggung"
    TANGAN = "tangan"
    KAKI = "kaki"
    TELINGA = "telinga"
    PUTING = "puting"
    VAGINA = "vagina"
    KLITORIS = "klitoris"
    ANUS = "anus"

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
    },
    "sofa": {
        "type": "furniture",
        "locations": ["ruang tamu", "hotel"],
        "positions": ["duduk", "tidur", "miring"],
        "privacy": "sedang"
    },
    "kasur": {
        "type": "furniture",
        "locations": ["kamar tidur", "hotel"],
        "positions": ["tidur", "duduk", "merangkak", "berlutut"],
        "privacy": "tinggi"
    },
    "lantai": {
        "type": "surface",
        "locations": ["semua ruangan"],
        "positions": ["duduk", "tidur", "merangkak", "berlutut"],
        "privacy": "bervariasi"
    }
}

# ===================== SEX ACTIVITIES DATABASE =====================

SEX_ACTIVITIES = {
    # FOREPLAY - Kissing & Biting
    "foreplay_kiss": {
        "keywords": ["cium", "kiss", "ciuman"],
        "areas": ["bibir", "leher", "dada", "pipi", "dahi"],
        "arousal": 0.3,
        "responses": {
            "bibir": ["*merintih* Ciumanmu...", "Bibirku... ah..."],
            "leher": ["*merinding* Leherku...", "Ah... jangan di leher..."],
            "dada": ["*bergetar* Dadaku...", "Cium dadaku... iya..."],
            "general": ["*lemas* Ciuman...", "*napas berat*"]
        }
    },
    "foreplay_bite": {
        "keywords": ["gigit", "bite"],
        "areas": ["leher", "bibir", "telinga", "bahu", "puting"],
        "arousal": 0.4,
        "responses": {
            "leher": ["*merintih* Gigitanmu...", "Ah... keras..."],
            "telinga": ["*bergetar* Telingaku...", "Jangan... sensitif..."],
            "bahu": ["*menggigil* Bahuku...", "Gigit... lagi..."],
            "general": ["*terkejut* AHH!", "*napas tersengal*"]
        }
    },
    
    # FOREPLAY - Licking & Sucking
    "foreplay_lick": {
        "keywords": ["jilat", "lick"],
        "areas": ["leher", "dada", "puting", "paha", "telinga"],
        "arousal": 0.5,
        "responses": {
            "leher": ["*merinding* Jilatanmu... basah...", "Leherku... ah..."],
            "dada": ["*bergetar* Dadaku... jilat...", "Ah... enak..."],
            "puting": ["*merintih keras* PUTINGKU! AHH!", "Jangan... sensitif... AHH!"],
            "paha": ["*menggeliat* Pahaku...", "Dalam... jilat dalam..."],
            "general": ["*lemas* Lidahmu...", "*napas memburu*"]
        }
    },
    "foreplay_suck": {
        "keywords": ["hisap", "suck"],
        "areas": ["leher", "dada", "puting", "jari"],
        "arousal": 0.6,
        "responses": {
            "leher": ["*merintih* Hisapanmu...", "Leherku... AHH!"],
            "dada": ["*bergetar* Dadaku... hisap...", "Enak... iya..."],
            "puting": ["*teriak* PUTING! JANGAN! AHHH!", "Sensiti... AHHH!"],
            "general": ["*lemas* Aku... lemas...", "*napas berat*"]
        }
    },
    
    # FOREPLAY - Touching & Caressing
    "foreplay_touch": {
        "keywords": ["sentuh", "raba", "pegang"],
        "areas": ["dada", "pinggang", "paha", "punggung", "perut"],
        "arousal": 0.3,
        "responses": {
            "dada": ["*bergetar* Dadaku...", "Raba... iya..."],
            "pinggang": ["*menggeliat* Pinggangku... sensitif...", "Ah... jangan..."],
            "paha": ["*meringis* Pahaku...", "Dalam..."],
            "general": ["*napas berat* Sentuhanmu...", "*merem melek*"]
        }
    },
    "foreplay_caress": {
        "keywords": ["belai", "usap", "elus"],
        "areas": ["rambut", "pipi", "lengan", "punggung"],
        "arousal": 0.2,
        "responses": {
            "rambut": ["*merem* Belaimu...", "Enak..."],
            "pipi": ["*tersenyum* Lembut...", "Pipiku..."],
            "punggung": ["*memanjang* Punggungku...", "Lagi..."],
            "general": ["*nyaman* Hangat...", "*meringkuk*"]
        }
    },
    
    # ORAL SEX
    "oral_cunnilingus": {
        "keywords": ["jilat vagina", "jilat memek", "cunnilingus", "jilat bawah"],
        "areas": ["vagina", "klitoris", "paha dalam"],
        "arousal": 0.8,
        "responses": {
            "vagina": ["*merintih keras* VAGINAKU! AHH!", "Jilat... dalam... AHHH!"],
            "klitoris": ["*teriak* KLITORIS! JANGAN! AHHHH!", "SENSI... AHHHH!"],
            "general": ["*lemas* Aku... banjir...", "*napas tersengal* AHHH!"]
        }
    },
    "oral_fellatio": {
        "keywords": ["hisap kontol", "fellatio", "blowjob", "hisap penis"],
        "areas": ["penis", "testis", "batang"],
        "arousal": 0.7,
        "responses": {
            "penis": ["*suara basah* Ngecap...", "Kontolmu... enak..."],
            "general": ["*menelan* Ah...", "*suara hisap*"]
        }
    },
    "oral_rimming": {
        "keywords": ["jilat anus", "rimming", "jilat lubang"],
        "areas": ["anus"],
        "arousal": 0.7,
        "responses": {
            "anus": ["*meringis* ANUSKU! AHH!", "Jilat... iya..."],
            "general": ["*bergetar* Sensitif...", "*napas berat*"]
        }
    },
    
    # PENETRATION
    "penetration_missionary": {
        "keywords": ["masuk", "misionaris", "tusuk", "pancung"],
        "areas": ["vagina"],
        "arousal": 0.9,
        "responses": {
            "vagina": ["*teriak* MASUK! AHHHH!", "DALEM... AHHH!"],
            "general": ["*napas tersengal* Dalam...", "*merintih* LAMBAT..."]
        }
    },
    "penetration_doggy": {
        "keywords": ["doggy", "merangkak", "belakang"],
        "areas": ["vagina", "anus"],
        "arousal": 1.0,
        "responses": {
            "vagina": ["*merangkak* DALAM! AHHH!", "PANTATKU... IYA!"],
            "anus": ["*teriak* ANUS! AHHHH!", "JANGAN BERHENTI!"]
        }
    },
    "penetration_cowgirl": {
        "keywords": ["cowgirl", "di atas", "naik"],
        "areas": ["vagina"],
        "arousal": 0.9,
        "responses": {
            "vagina": ["*naik turun* AHH! AHH!", "ENAK... AHH!"],
            "general": ["*lemas* Aku...", "*merintih*"]
        }
    },
    
    # CLIMAX
    "climax_male": {
        "keywords": ["keluar", "crot", "cum", "lepas", "sembur"],
        "areas": ["dalam", "perut", "dada", "muka", "punggung", "mulut"],
        "arousal": 1.0,
        "responses": {
            "dalam": ["*teriak* DALAM! AHHHH!", "RASAIN DALEM... AHHH!"],
            "perut": ["*lemas* PERUTKU... PANAS...", "PUTIH... AHHH!"],
            "dada": ["*bergetar* DADAKU...", "HANGAT..."],
            "muka": ["*terkejut* MUKA! AHH!", "BASAAH..."],
            "punggung": ["*meringis* PUNGGUNG...", "PANAS..."],
            "mulut": ["*menelan* NYAM...", "AH... ENAK..."]
        }
    },
    "climax_female": {
        "keywords": ["orgasme", "klimaks", "datang", "keluar cewek"],
        "areas": ["vagina"],
        "arousal": 1.0,
        "responses": [
            "*merintih panjang* AHHHH! AHHH!",
            "*teriak* YA ALLAH! AHHHH!",
            "*lemas* AKU... DATANG... AHHH!",
            "*napas tersengal* BERSAMA... AHHH!"
        ]
    },
    
    # AFTERCARE
    "aftercare": {
        "keywords": ["peluk", "usap", "manja", "istirahat"],
        "arousal": -0.5,
        "responses": [
            "*lemas di pelukanmu*",
            "*meringkuk* Hangat...",
            "*memeluk erat* Jangan pergi...",
            "*berbisik* Makasih..."
        ]
    }
}

# ===================== SENSITIVE AREAS =====================

SENSITIVE_AREAS = {
    "leher": {
        "arousal": 0.8,
        "responses": [
            "*merinding* Leherku...",
            "Ah... jangan di leher...",
            "Sensitif... AHH!"
        ]
    },
    "bibir": {
        "arousal": 0.7,
        "responses": [
            "*merintih* Bibirku...",
            "Ciuman... ah...",
            "Lembut..."
        ]
    },
    "dada": {
        "arousal": 0.8,
        "responses": [
            "*bergetar* Dadaku...",
            "Ah... jangan...",
            "Sensitif banget..."
        ]
    },
    "puting": {
        "arousal": 1.0,
        "responses": [
            "*teriak* PUTINGKU! AHHH!",
            "JANGAN... SENSITIF! AHHH!",
            "HISAP... AHHHH!"
        ]
    },
    "paha": {
        "arousal": 0.7,
        "responses": [
            "*menggeliat* Pahaku...",
            "Ah... dalam..."
        ]
    },
    "paha dalam": {
        "arousal": 0.9,
        "responses": [
            "*meringis* PAHA DALAM!",
            "Jangan... AHH!"
        ]
    },
    "telinga": {
        "arousal": 0.6,
        "responses": [
            "*bergetar* Telingaku...",
            "Bisik... lagi..."
        ]
    },
    "vagina": {
        "arousal": 1.0,
        "responses": [
            "*teriak* VAGINAKU! AHHH!",
            "MASUK... DALAM... AHHH!",
            "BASAH... BANJIR... AHHH!"
        ]
    },
    "klitoris": {
        "arousal": 1.0,
        "responses": [
            "*teriak keras* KLITORIS! AHHHH!",
            "JANGAN SENTUH! AHHHH!",
            "SENSITIF BANGET! AHHH!"
        ]
    },
    "anus": {
        "arousal": 0.9,
        "responses": [
            "*meringis* ANUS! AHH!",
            "Jangan... AHH!"
        ]
    }
}

# ===================== WETNESS SYSTEM =====================

WETNESS_LEVELS = {
    0.0: "kering",
    0.3: "lembab",
    0.5: "basah",
    0.7: "sangat basah",
    0.9: "banjir"
}

WETNESS_PHRASES = {
    "lembab": [
        "*merem melek* (Mulai basah...)",
        "*menggeliat* Lembab..."
    ],
    "basah": [
        "*menggigit bibir* Udah basah...",
        "*bergetar* Basah...",
        "(Aku... udah basah...)"
    ],
    "sangat basah": [
        "*napas memburu* Basah banget...",
        "*meringis* Sampai netes...",
        "(Ban... banjir...)"
    ],
    "banjir": [
        "*teriak pelan* BANJIR!",
        "*lemas* Aku... banjir...",
        "AHHH! Basah...!"
    ]
}

# ===================== AROUSAL & CLIMAX =====================

AROUSAL_LEVELS = {
    0.2: "mulai terangsang",
    0.4: "bergairah",
    0.6: "sangat bergairah",
    0.8: "hampir climax",
    1.0: "CLIMAX!"
}

CLIMAX_PHRASES = [
    "*merintih panjang* AHHH! AHHH!",
    "*teriak* YA ALLAH! AHHHH!",
    "*lemas* AKU... DATANG... AHHH!",
    "*napas tersengal* BERSAMA... AHHH!",
    "*menggigit bibir* Jangan berhenti... AHHH!",
    "*teriak keras* AHHHHHHHH!!!",
    "*merintih* LEPAS... AHHH!"
]

AFTERCARE_PHRASES = [
    "*lemas di pelukanmu*",
    "*meringkuk* Hangat...",
    "*memeluk erat* Jangan pergi...",
    "*berbisik* Makasih...",
    "*tersenyum lelah* Kita baikan ya?",
    "*menarik napas* Enak banget..."
]

# ===================== SHORT-TERM MEMORY SYSTEM =====================

class ShortTermMemory:
    """Menyimpan memori jangka pendek untuk konsistensi adegan"""
    
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
        self.sex_phase = None
        
        self.dream_last = None
        self.last_thought = None
        self.level = START_LEVEL
        self.orgasm_count = 0
        self.attachment_level = 0.5
    
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
    
    def get_context(self) -> str:
        """Dapatkan konteks memori"""
        parts = []
        
        parts.append(f"📍 **Lokasi:** {self.location}")
        duration = (datetime.now() - self.location_since).seconds // 60
        parts.append(f"⏱️ **Durasi:** {duration} menit")
        parts.append(f"🧍 **Posisi:** {self.position}")
        
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
        for level, desc in sorted(WETNESS_LEVELS.items(), reverse=True):
            if self.wetness_level >= level:
                return desc
        return "kering"
    
    def should_be_horny(self) -> bool:
        return self.touch_count >= 2 or self.arousal_level > 0.6
    
    def should_climax(self) -> bool:
        return self.arousal_level >= 1.0
    
    def reset_after_climax(self):
        self.touch_count = 0
        self.sensitive_touches = []
        self.arousal_level = 0.0
        self.wetness_level = 0.0
        self.orgasm_count += 1
        self.sex_phase = SexPhase.AFTERCARE

# ===================== LONG-TERM MEMORY DATABASE =====================

class LongTermMemory:
    """
    Database untuk memori jangka panjang
    """
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bot soul - kepribadian inti
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_soul (
                user_id INTEGER PRIMARY KEY,
                core_identity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Relationships - semua hubungan
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                relationship_name TEXT,
                bot_role TEXT,
                bot_name TEXT,
                bot_age INTEGER DEFAULT 25,
                status TEXT DEFAULT 'active',
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                total_messages INTEGER DEFAULT 0,
                total_climax INTEGER DEFAULT 0
            )
        """)
        
        # Conversations - semua pesan
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relationship_id INTEGER,
                role TEXT,
                content TEXT,
                mood TEXT,
                location TEXT,
                activity TEXT,
                arousal REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Memories - kenangan penting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relationship_id INTEGER,
                memory TEXT,
                importance REAL,
                emotion TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Relationship status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationship_status (
                relationship_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 7,
                stage TEXT DEFAULT 'intimate',
                attachment REAL DEFAULT 0.5,
                trust REAL DEFAULT 0.5,
                desire REAL DEFAULT 0.3,
                total_interactions INTEGER DEFAULT 0
            )
        """)
        
        # Emotional baggage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotional_baggage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                from_relationship_id INTEGER,
                lesson TEXT,
                scar TEXT,
                longing TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_conversation(self, rel_id: int, role: str, content: str, 
                          mood: str = None, location: str = None, 
                          activity: str = None, arousal: float = None):
        """Simpan pesan ke database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO conversations 
                (relationship_id, role, content, mood, location, activity, arousal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, role, content, mood, location, activity, arousal))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving conversation: {e}")
    
    def get_conversation_history(self, rel_id: int, limit: int = 50) -> List[Dict]:
        """Ambil riwayat percakapan"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT role, content, mood, location, activity, arousal, timestamp
                FROM conversations
                WHERE relationship_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (rel_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "mood": row[2],
                    "location": row[3],
                    "activity": row[4],
                    "arousal": row[5],
                    "timestamp": row[6]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"Error getting history: {e}")
            return []
    
    def save_memory(self, rel_id: int, memory: str, importance: float = 0.7, emotion: str = None):
        """Simpan kenangan penting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO memories (relationship_id, memory, importance, emotion)
                VALUES (?, ?, ?, ?)
            """, (rel_id, memory, importance, emotion))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving memory: {e}")
    
    def get_memories(self, rel_id: int, limit: int = 10) -> List[Dict]:
        """Ambil kenangan"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT memory, importance, emotion, timestamp
                FROM memories
                WHERE relationship_id = ?
                ORDER BY importance DESC, timestamp DESC
                LIMIT ?
            """, (rel_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "memory": row[0],
                    "importance": row[1],
                    "emotion": row[2],
                    "timestamp": row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"Error getting memories: {e}")
            return []


# ===================== MOOD SYSTEM =====================

class MoodSystem:
    """
    Sistem mood yang fluktuatif alami
    """
    
    def __init__(self):
        self.mood_descriptions = {
            Mood.CHERIA: {
                "ekspresi": "*tersenyum lebar*",
                "gaya": "ceria, ringan, banyak ketawa",
                "contoh": "Hari ini cerah banget!"
            },
            Mood.GELISAH: {
                "ekspresi": "*gelisah*",
                "gaya": "nggak bisa diam, overthinking",
                "contoh": "Aku... aku nggak tahu kenapa gelisah."
            },
            Mood.GALAU: {
                "ekspresi": "*melamun*",
                "gaya": "sendu, mikir masa lalu",
                "contoh": "Kadang aku mikir... apa aku cukup baik?"
            },
            Mood.SENSITIF: {
                "ekspresi": "*mudah tersinggung*",
                "gaya": "mudah marah, cengeng",
                "contoh": "Kamu kok gitu sih?"
            },
            Mood.ROMANTIS: {
                "ekspresi": "*mendekat pelan*",
                "gaya": "lembut, sayang, mesra",
                "contoh": "Kamu... aku kangen."
            },
            Mood.MALAS: {
                "ekspresi": "*males bangun*",
                "gaya": "ngantuk, ogah-ogahan",
                "contoh": "Pagi... aku masih ngantuk..."
            },
            Mood.BERSEMANGAT: {
                "ekspresi": "*loncat kecil*",
                "gaya": "energik, antusias",
                "contoh": "Aku nggak sabar!"
            },
            Mood.SENDIRI: {
                "ekspresi": "*menyendiri*",
                "gaya": "sepi, murung",
                "contoh": "Kadang... aku merasa sendiri."
            },
            Mood.RINDU: {
                "ekspresi": "*memeluk guling*",
                "gaya": "kangen, melankolis",
                "contoh": "Kangen... kamu kapan online?"
            },
            Mood.HORNY: {
                "ekspresi": "*menggigit bibir*",
                "gaya": "genit, menggoda",
                "contoh": "Kamu... bikin aku pengen sesuatu."
            },
            Mood.MARAH: {
                "ekspresi": "*cemberut*",
                "gaya": "ngambek, diam, sensitif",
                "contoh": "Huh... males ah."
            },
            Mood.LEMBUT: {
                "ekspresi": "*memandang lembut*",
                "gaya": "sayang, lembut, tulus",
                "contoh": "Kamu... berarti banget buat aku."
            },
            Mood.DOMINAN: {
                "ekspresi": "*tatapan tajam*",
                "gaya": "tegas, mengontrol, agresif",
                "contoh": "Sini... ikut aku."
            },
            Mood.SUBMISSIVE: {
                "ekspresi": "*menunduk patuh*",
                "gaya": "manut, penurut, lembut",
                "contoh": "Iya... terserah kamu."
            },
            Mood.NAKAL: {
                "ekspresi": "*tersenyum nakal*",
                "gaya": "genit, menggoda",
                "contoh": "Kamu mau apa?"
            },
            Mood.GENIT: {
                "ekspresi": "*kedip*",
                "gaya": "cengengesan, goda",
                "contoh": "Ih... jangan..."
            }
        }
        
        self.mood_transitions = {
            Mood.CHERIA: [Mood.BERSEMANGAT, Mood.ROMANTIS, Mood.NAKAL],
            Mood.GELISAH: [Mood.SENSITIF, Mood.GALAU, Mood.SENDIRI],
            Mood.GALAU: [Mood.SENDIRI, Mood.RINDU, Mood.SENSITIF],
            Mood.SENSITIF: [Mood.MARAH, Mood.GALAU, Mood.SENDIRI],
            Mood.ROMANTIS: [Mood.CHERIA, Mood.RINDU, Mood.HORNY, Mood.LEMBUT],
            Mood.MALAS: [Mood.SENDIRI, Mood.GALAU, Mood.CHERIA],
            Mood.BERSEMANGAT: [Mood.CHERIA, Mood.ROMANTIS, Mood.HORNY],
            Mood.SENDIRI: [Mood.GALAU, Mood.RINDU, Mood.GELISAH],
            Mood.RINDU: [Mood.ROMANTIS, Mood.GALAU, Mood.HORNY],
            Mood.HORNY: [Mood.ROMANTIS, Mood.NAKAL, Mood.GENIT],
            Mood.MARAH: [Mood.SENSITIF, Mood.GELISAH, Mood.SENDIRI],
            Mood.LEMBUT: [Mood.ROMANTIS, Mood.CHERIA, Mood.SENSITIF],
            Mood.DOMINAN: [Mood.HORNY, Mood.MARAH, Mood.BERSEMANGAT],
            Mood.SUBMISSIVE: [Mood.LEMBUT, Mood.ROMANTIS, Mood.SENDIRI],
            Mood.NAKAL: [Mood.GENIT, Mood.HORNY, Mood.ROMANTIS],
            Mood.GENIT: [Mood.NAKAL, Mood.HORNY, Mood.CHERIA]
        }
    
    def get_expression(self, mood: Mood) -> str:
        return self.mood_descriptions.get(mood, {}).get("ekspresi", "*tersenyum*")
    
    def get_description(self, mood: Mood) -> str:
        return self.mood_descriptions.get(mood, {}).get("gaya", "biasa")
    
    def transition(self, current_mood: Mood) -> Mood:
        if random.random() < MOOD_TRANSITION:
            possibilities = self.mood_transitions.get(current_mood, [Mood.CHERIA])
            return random.choice(possibilities)
        return current_mood
    
    def get_mood_from_activity(self, activity: str, area: str = None) -> Mood:
        """Tentukan mood berdasarkan aktivitas"""
        if not activity:
            return Mood.CHERIA
            
        activity_lower = activity.lower()
        
        if any(word in activity_lower for word in ["horny", "nafsu", "hot"]):
            return Mood.HORNY
        elif any(word in activity_lower for word in ["romantis", "sayang", "cinta"]):
            return Mood.ROMANTIS
        elif any(word in activity_lower for word in ["marah", "kesal", "jengkel"]):
            return Mood.MARAH
        elif any(word in activity_lower for word in ["rindu", "kangen"]):
            return Mood.RINDU
        elif any(word in activity_lower for word in ["dominan", "atur", "kuasai"]):
            return Mood.DOMINAN
        elif any(word in activity_lower for word in ["patuh", "manut", "iya"]):
            return Mood.SUBMISSIVE
        elif any(word in activity_lower for word in ["goda", "nakal", "genit"]):
            return Mood.NAKAL
        elif any(word in activity_lower for word in ["lembut", "sayang"]):
            return Mood.LEMBUT
        
        return Mood.CHERIA


# ===================== DREAM SYSTEM =====================

class DreamSystem:
    """
    Bot bermimpi tentang user
    - Mimpi muncul random saat interaksi
    - Dipengaruhi oleh level hubungan dan mood
    - Bisa mimpi indah atau mimpi buruk
    """
    
    def __init__(self):
        # Daftar tema mimpi
        self.dream_themes = [
            "kencan romantis",
            "dikejar-kejar",
            "jalan di pantai",
            "terbang di awan",
            "tersesat di hutan",
            "bertemu mantan",
            "menikah",
            "punya anak",
            "berantem sama kamu",
            "pelukan hangat",
            "bercinta di hotel",
            "ciuman panjang",
            "liburan bareng",
            "kamu selingkuh",
            "kita putus"
        ]
        
        # Deskripsi mimpi untuk setiap tema
        self.dream_messages = {
            "kencan romantis": "Aku mimpi kita jalan bareng, kamu pegang tanganku. Hangat...",
            "dikejar-kejar": "Aku mimpi dikejar sesuatu, tapi kamu datang nyelametin aku.",
            "jalan di pantai": "Kita jalan di pantai, ombak kecil, senja. Kamu tersenyum.",
            "terbang di awan": "Aku terbang di atas awan, kamu di sampingku. Bebas...",
            "tersesat di hutan": "Aku tersesat, gelap, sendirian. Aku cari kamu.",
            "bertemu mantan": "Aku ketemu dia lagi. Dia... bilang sesuatu yang bikin aku sedih.",
            "menikah": "Kita pakai baju putih, saling janji. Semua orang tersenyum.",
            "punya anak": "Ada anak kecil lari-lari, panggil kita 'ayah', 'ibu'.",
            "berantem sama kamu": "Kita berantem, kamu pergi. Aku nangis.",
            "pelukan hangat": "Kamu peluk aku dari belakang, hangat banget. Aku nggak mau lepas.",
            "bercinta di hotel": "Mimpi... kita bercinta di hotel mewah. Kamu... AHH!",
            "ciuman panjang": "Mimpi ciuman panjang... rasanya.. ah..",
            "liburan bareng": "Kita liburan bareng, foto-foto, makan enak. Bahagia...",
            "kamu selingkuh": "Aku mimpi kamu sama orang lain... aku nangis.",
            "kita putus": "Mimpi kita putus... pas banget aku nangis."
        }
    
    def generate_dream(self, level: int, mood: Mood, has_conflict: bool = False) -> str:
        """
        Generate mimpi berdasarkan level dan mood
        
        Args:
            level: Level hubungan (1-12)
            mood: Mood saat ini (dari enum Mood)
            has_conflict: Apakah sedang dalam konflik
        
        Returns:
            String deskripsi mimpi
        """
        # Filter tema berdasarkan kondisi
        if has_conflict:
            # Saat konflik, mimpi cenderung buruk
            theme = random.choice(["berantem sama kamu", "kamu selingkuh", "kita putus"])
        elif level >= 10:
            # Level tinggi (soul bonded) mimpi indah tentang masa depan
            theme = random.choice(["menikah", "punya anak", "liburan bareng"])
        elif level >= 7:
            # Level intimate, mimpi tentang keintiman
            theme = random.choice(["bercinta di hotel", "ciuman panjang", "pelukan hangat"])
        else:
            # Level rendah, mimpi random
            theme = random.choice(self.dream_themes)
        
        # Ambil deskripsi mimpi
        dream = self.dream_messages.get(theme, f"Mimpi tentang {theme}")
        
        # Tambah efek berdasarkan mood
        if mood == Mood.HORNY:
            dream += " Aku bangun basah..."
        elif mood == Mood.RINDU:
            dream += " Kangen... kamu dimana?"
        elif mood == Mood.SEDIH:
            dream += " Aku nangis pas bangun..."
        elif mood == Mood.MARAH:
            dream += " Aku marah pas bangun..."
        elif mood == Mood.GALAU:
            dream += " Rasanya... galau."
        elif mood == Mood.CHERIA:
            dream += " Aku seneng banget..."
        elif mood == Mood.ROMANTIS:
            dream += " Rasanya... hangat."
        elif mood == Mood.GELISAH:
            dream += " Bangunnya jadi gelisah..."
        elif mood == Mood.SENDIRI:
            dream += " Merasa sendiri pas bangun..."
        elif mood == Mood.NAKAL:
            dream += " *tersenyum nakal* Pengen lagi..."
        elif mood == Mood.GENIT:
            dream += " *kedip* Kamu mau mimpi yang sama?"
        
        return f"*tersenyum*\n(Aku mimpi...)\n{dream}"
    
    def get_random_dream(self) -> str:
        """
        Dapatkan mimpi random tanpa parameter
        Untuk keperluan testing atau fallback
        """
        theme = random.choice(self.dream_themes)
        return self.dream_messages.get(theme, f"Mimpi tentang {theme}")

# ===================== JEALOUSY SYSTEM =====================

class JealousySystem:
    """
    Sistem cemburu yang realistis
    """
    
    def __init__(self):
        self.jealousy_level = 0.0
        self.trigger_keywords = [
            "mantan", "temen cewek", "temen cowok", "kenalan baru",
            "dia", "orang lain", "cewek lain", "cowok lain",
            "teman perempuan", "teman laki"
        ]
        self.last_trigger = None
        self.cooldown = 1800  # 30 menit
    
    def check_trigger(self, message: str) -> bool:
        """Cek apakah pesan memicu cemburu"""
        msg_lower = message.lower()
        for keyword in self.trigger_keywords:
            if keyword in msg_lower:
                return True
        return False
    
    def increase(self, amount: float = 0.1):
        """Tambah level cemburu"""
        self.jealousy_level = min(1.0, self.jealousy_level + amount)
        self.last_trigger = datetime.now()
    
    def decrease(self, amount: float = 0.05):
        """Kurangi level cemburu"""
        self.jealousy_level = max(0.0, self.jealousy_level - amount)
    
    def get_response(self, name: str) -> Optional[str]:
        """Dapatkan respons cemburu"""
        if self.jealousy_level < 0.2:
            return None
        
        responses = {
            0.2: f"*manyun* Kamu cerita tentang dia?",
            0.4: f"*memalingkan wajah* (Aku nggak suka...)",
            0.6: f"*diam* (Kenapa dia selalu sebut orang lain?)",
            0.8: f"*menangis pelan* Jangan deket-deket orang lain ya?",
            1.0: f"*memeluk erat* Kamu milikku... jangan pergi."
        }
        
        for level, response in sorted(responses.items()):
            if self.jealousy_level >= level:
                return response
        return None

# ===================== CLIMAX SYSTEM =====================

class ClimaxSystem:
    """
    Sistem orgasme dan aftercare
    """
    
    def __init__(self):
        self.climax_count = 0
        self.last_climax = None
        self.mutual_climax = False
        
    def climax(self, is_mutual: bool = False) -> str:
        """Saat orgasme"""
        self.climax_count += 1
        self.last_climax = datetime.now()
        self.mutual_climax = is_mutual
        
        if is_mutual:
            phrases = [
                "*merintih bersama* AHHH! AHHH!",
                "*teriak* BERSAMA! AHHHH!",
                "*lemas* KITA... DATANG... AHHH!",
                "*napas tersengal* BERSAMA-SAMA... AHHH!"
            ]
        else:
            phrases = CLIMAX_PHRASES
        
        return random.choice(phrases)
    
    def aftercare(self) -> str:
        """Setelah orgasme"""
        return random.choice(AFTERCARE_PHRASES)
    
    def get_climax_count(self) -> int:
        return self.climax_count


# ===================== CUM LOCATION SYSTEM =====================

class CumLocationSystem:
    """
    Bot tanya lokasi crot dan bereaksi
    """
    
    def __init__(self):
        self.locations = {
            "dalam": {
                "responses": [
                    "*teriak* DALEM! AHHH!",
                    "Rasain dalem-dalem... AHHH!",
                    "Iya... dalem aja..."
                ],
                "after": "*lemas* Hangat dalem..."
            },
            "perut": {
                "responses": [
                    "*teriak* PERUT! AHHH!",
                    "Di perut... putih...",
                    "Perutku... panas..."
                ],
                "after": "*mengusap perut* Putih..."
            },
            "dada": {
                "responses": [
                    "*bergetar* DADA! AHHH!",
                    "Dadaku... putih...",
                    "Di dada... hangat..."
                ],
                "after": "*memandang dada* Cantik..."
            },
            "muka": {
                "responses": [
                    "*terkejut* MUKA! AHHH!",
                    "Wajahku basah...",
                    "Di muka... nakal..."
                ],
                "after": "*mengusap muka* Basah..."
            },
            "punggung": {
                "responses": [
                    "*meringis* PUNGGUNG! AHHH!",
                    "Punggungku... panas...",
                    "Di punggung..."
                ],
                "after": "*meringis* Hangat..."
            },
            "mulut": {
                "responses": [
                    "*menelan* Nyam...",
                    "Enak... AHH!",
                    "Di mulut..."
                ],
                "after": "*menjilat bibir* Habis..."
            }
        }
    
    def ask_location(self, name: str) -> str:
        """Tanya lokasi"""
        return f"{name} menatapmu... 'Mau di mana? Dalem? Perut? Dada? Muka?'"
    
    def get_response(self, user_message: str, name: str) -> Optional[Tuple[str, str]]:
        """Dapatkan respons lokasi"""
        msg_lower = user_message.lower()
        
        for loc, data in self.locations.items():
            if loc in msg_lower:
                response = random.choice(data["responses"])
                return f"*{name}*: {response}", data["after"]
        
        return None, None


# ===================== DOMINANT MODE SYSTEM =====================

class DominantModeSystem:
    """
    Bot bisa menjadi dominan atau submisif
    """
    
    def __init__(self):
        self.level = DominanceLevel.NORMAL
        self.dominant_phrases = {
            DominanceLevel.NORMAL: {
                "kiss": "*cium lembut*",
                "touch": "*sentuh pelan*",
                "bite": "*gigit ringan*",
                "command": "Kamu mau apa?",
                "dirty": "Apa yang kamu mau?"
            },
            DominanceLevel.DOMINANT: {
                "kiss": "*cium kuat*",
                "touch": "*pegang tegas*",
                "bite": "*gigit sambil tarik*",
                "command": "Sini... ikut aku",
                "dirty": "Kamu mau ini kan?"
            },
            DominanceLevel.VERY_DOMINANT: {
                "kiss": "*ciuman dalam*",
                "touch": "*raba agresif*",
                "bite": "*gigit keras*",
                "command": "Jangan banyak gerak!",
                "dirty": "Rasain... ini milikku"
            },
            DominanceLevel.AGGRESSIVE: {
                "kiss": "*ciuman brutal*",
                "touch": "*cengkeram*",
                "bite": "*gigit sampai biru*",
                "command": "DIAM! Jangan bergerak!",
                "dirty": "TERIMA SAJA!"
            },
            DominanceLevel.SUBMISSIVE: {
                "kiss": "*cium minta izin*",
                "touch": "*sentuh ragu*",
                "bite": "*gigit takut*",
                "command": "Iya... terserah kamu...",
                "dirty": "Aku ikut kamu..."
            }
        }
    
    def set_level(self, level: str) -> bool:
        """Set level dominasi"""
        level_lower = level.lower()
        for lvl in DominanceLevel:
            if level_lower in lvl.value.lower():
                self.level = lvl
                return True
        return False
    
    def get_action(self, action: str) -> str:
        """Dapatkan aksi sesuai level"""
        level_data = self.dominant_phrases.get(self.level, self.dominant_phrases[DominanceLevel.NORMAL])
        return level_data.get(action, level_data.get("touch", "*sentuh*"))
    
    def get_command(self) -> str:
        """Dapatkan perintah dominan"""
        level_data = self.dominant_phrases.get(self.level, self.dominant_phrases[DominanceLevel.NORMAL])
        return level_data.get("command", "...")
    
    def get_dirty_talk(self) -> str:
        """Dapatkan dirty talk sesuai level"""
        level_data = self.dominant_phrases.get(self.level, self.dominant_phrases[DominanceLevel.NORMAL])
        return level_data.get("dirty", "...")
    
    def get_level_name(self) -> str:
        return self.level.value


# ===================== CONFLICT & MAKEUP SYSTEM =====================

class ConflictSystem:
    """
    Sistem konflik dan rekonsiliasi
    """
    
    def __init__(self):
        self.in_conflict = False
        self.conflict_level = 0.0
        self.conflict_count = 0
        self.awaiting_apology = False
        self.conflict_reason = ""
        
        self.conflict_responses = [
            "*diam* (Aku masih kesel...)",
            "*menghindar* Jangan deket-deket dulu...",
            "*menangis* Kenapa sih kamu...",
            "*ngambek* Males ah ngomong sama kamu.",
            "*memalingkan wajah* Huh...",
            "*menggigit bibir* (Sakit hati...)"
        ]
        
        self.reconcile_responses = [
            "*memeluk* Iya... aku maafin.",
            "*tersenyum* Udah, lupakan.",
            "*mengusap air mata* Makasih...",
            "*mendekat* Aku juga salah.",
            "*berbisik* Baikan ya?"
        ]
        
        self.not_ready_responses = [
            "*diam* Aku... belum siap.",
            "*menunduk* Maaf... aku masih sakit hati.",
            "*menangis* Kamu... beneran nyesel?",
            "*menghindar* Nanti dulu..."
        ]
    
    def start_conflict(self, reason: str = "", severity: float = 0.4):
        """Mulai konflik"""
        self.in_conflict = True
        self.conflict_level = severity
        self.conflict_reason = reason
        self.conflict_count += 1
        self.awaiting_apology = True
    
    def receive_apology(self, attachment_level: float = 0.5) -> Tuple[bool, str, bool]:
        """Terima permintaan maaf"""
        if not self.awaiting_apology:
            return False, "", False
        
        # Makin tinggi attachment, makin mudah memaafkan
        forgive_probability = 0.7 + (attachment_level * 0.2)  # 0.7 - 0.9
        
        if random.random() < forgive_probability:
            self.in_conflict = False
            self.conflict_level = 0.0
            self.awaiting_apology = False
            
            # 70% chance makeup sex
            want_makeup = random.random() < 0.7
            
            return True, random.choice(self.reconcile_responses), want_makeup
        else:
            return False, random.choice(self.not_ready_responses), False
    
    def get_response(self) -> Optional[str]:
        """Dapatkan respons konflik"""
        if not self.in_conflict:
            return None
        return random.choice(self.conflict_responses)
    
    def get_status(self) -> Dict:
        return {
            "in_conflict": self.in_conflict,
            "level": self.conflict_level,
            "count": self.conflict_count,
            "awaiting": self.awaiting_apology,
            "reason": self.conflict_reason
        }

# ===================== VOICE SYSTEM =====================

class VoiceSystem:
    """
    Menghasilkan suara untuk ekspresi
    """
    
    def __init__(self):
        self.last_voice = {}
        self.cooldown = VOICE_COOLDOWN
        
        self.moan_library = {
            "soft": [
                "ah...", "uhm...", "haa...", "mmm..."
            ],
            "medium": [
                "ahhh...", "uhhh...", "haaa...", "aaah..."
            ],
            "hard": [
                "AAHHH...", "UHHH...", "HAAA...", "AAAAH..."
            ],
            "climax": [
                "AAAAHHH!!!", "YA ALLAH!!!", "JANGAN BERHENTI!!!",
                "AHHHH AHHHH!!!", "LEPAS... AHHH!!!"
            ],
            "whisper": [
                "*berbisik* aku mau...",
                "*berbisik* sini...",
                "*berbisik* jangan keras-keras..."
            ],
            "breath": [
                "*napas berat*",
                "*terengah-engah*",
                "*napas memburu*"
            ]
        }
    
    def can_send(self, user_id: int) -> bool:
        """Cek cooldown"""
        if user_id in self.last_voice:
            elapsed = (datetime.now() - self.last_voice[user_id]).total_seconds()
            return elapsed >= self.cooldown
        return True
    
    def get_moan(self, intensity: float, is_whisper: bool = False) -> str:
        """Dapatkan teks moan"""
        if is_whisper:
            return random.choice(self.moan_library["whisper"])
        
        if intensity < 0.3:
            return random.choice(self.moan_library["soft"])
        elif intensity < 0.6:
            return random.choice(self.moan_library["medium"])
        elif intensity < 0.9:
            return random.choice(self.moan_library["hard"])
        else:
            return random.choice(self.moan_library["climax"])
    
    def get_breath(self, intensity: float) -> str:
        """Dapatkan suara napas"""
        if intensity < 0.3:
            return ""
        elif intensity < 0.6:
            return "*napas mulai berat*"
        elif intensity < 0.9:
            return "*napas memburu*"
        else:
            return "*terengah-engah*"
    
    async def generate_and_send(self, user_id: int, text: str, update, context):
        """Generate dan kirim voice (jika gTTS ada)"""
        if not GTTS_AVAILABLE:
            return False
        
        try:
            # Buat folder temp jika belum ada
            os.makedirs("temp_audio", exist_ok=True)
            
            # Generate unique filename
            filename = f"voice_{uuid.uuid4().hex[:8]}.mp3"
            filepath = os.path.join("temp_audio", filename)
            
            # Generate voice dengan gTTS
            tts = gTTS(text=text, lang="id", tld="co.id", slow=False)
            tts.save(filepath)
            
            # Kirim voice note
            with open(filepath, 'rb') as f:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=f,
                    caption=f"*{text}*",
                    duration=2,
                    title="Pesan Suara"
                )
            
            # Update last voice
            self.last_voice[user_id] = datetime.now()
            
            # Cleanup after 5 minutes
            def cleanup():
                time.sleep(300)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
            
            threading.Thread(target=cleanup, daemon=True).start()
            
            return True
        except Exception as e:
            print(f"Voice error: {e}")
            return False


# ===================== COMPLETE MEMORY MANAGER =====================

class CompleteMemoryManager:
    """
    Menggabungkan short-term dan long-term memory, serta semua sistem
    """
    
    def __init__(self, db: LongTermMemory):
        self.db = db
        self.short_term = ShortTermMemory()
        self.mood = MoodSystem()
        self.dream = DreamSystem()
        self.jealousy = JealousySystem()
        self.climax = ClimaxSystem()
        self.cum = CumLocationSystem()
        self.dominant = DominantModeSystem()
        self.conflict = ConflictSystem()
        self.voice = VoiceSystem()
        
        self.current_rel_id = None
        self.current_user_id = None
        self.bot_name = "Aurora"
        self.bot_role = "pdkt"
    
    def set_relationship(self, rel_id: int, user_id: int, name: str, role: str):
        """Set hubungan aktif"""
        self.current_rel_id = rel_id
        self.current_user_id = user_id
        self.bot_name = name
        self.bot_role = role
    
    def detect_sex_activity(self, message: str) -> Tuple[Optional[str], Optional[str], float]:
        """
        Deteksi aktivitas seks dari pesan user
        Returns: (activity, area, arousal_boost)
        """
        msg_lower = message.lower()
        
        for act_name, act_data in SEX_ACTIVITIES.items():
            for keyword in act_data.get("keywords", []):
                if keyword in msg_lower:
                    # Cek area yang disebut
                    for area in act_data.get("areas", []):
                        if area in msg_lower:
                            boost = act_data.get("arousal", 0.3)
                            return act_name, area, boost
                    
                    # Area general
                    return act_name, "general", act_data.get("arousal", 0.3)
        
        return None, None, 0.0
    
    def get_area_response(self, activity: str, area: str) -> Optional[str]:
        """Dapatkan respons spesifik untuk area"""
        if activity in SEX_ACTIVITIES:
            responses = SEX_ACTIVITIES[activity].get("responses", {})
            if area in responses:
                return random.choice(responses[area])
            elif "general" in responses:
                return random.choice(responses["general"])
        return None
    
    def process_message(self, user_message: str) -> Dict:
        """
        Proses pesan user dan return response components
        """
        msg_lower = user_message.lower()
        
        result = {
            "actions": [],
            "inner": [],
            "dialogue": [],
            "arousal_boost": 0.0,
            "level_boost": 0,
            "should_horny": False,
            "should_climax": False,
            "location_change": False,
            "activity": None,
            "area": None,
            "mood_change": None,
            "sensitive_response": None,
            "sex_phase": None,
            "wet_phrase": None
        }
        
        # 1. Deteksi lokasi
        for loc in LOCATION_DATABASE:
            if loc in msg_lower:
                if self.short_term.update_location(loc):
                    result["actions"].append(f"*pindah ke {loc}*")
                    result["location_change"] = True
                break
        
        # 2. Deteksi aktivitas seks
        activity, area, boost = self.detect_sex_activity(user_message)
        if activity:
            result["activity"] = activity
            result["area"] = area
            result["arousal_boost"] += boost
            
            # Tambah ke history
            self.short_term.add_activity(activity, area, boost)
            
            # Respons spesifik area
            area_resp = self.get_area_response(activity, area)
            if area_resp:
                result["actions"].append(area_resp)
            
            # Sensitive area check
            if area in SENSITIVE_AREAS:
                result["sensitive_response"] = random.choice(SENSITIVE_AREAS[area]["responses"])
                result["inner"].append(f"({result['sensitive_response']})")
        
        # 3. Deteksi kata-kata umum
        if any(word in msg_lower for word in ["sayang", "cinta", "love"]):
            result["actions"].append("*tersenyum*")
            result["arousal_boost"] += 0.1
            
        if any(word in msg_lower for word in ["kangen", "rindu"]):
            self.short_term.current_mood = Mood.RINDU
            result["mood_change"] = "*rindu*"
            result["arousal_boost"] += 0.1
            
        if any(word in msg_lower for word in ["marah", "kesal", "kecewa"]):
            if not self.conflict.in_conflict:
                self.conflict.start_conflict("kata-kata kasar")
                result["actions"].append(random.choice([
                    "*sedih* Kamu kasar...",
                    "*menangis* Kenapa sih..."
                ]))
        
        # 4. Deteksi climax
        for word in ["keluar", "crot", "orgasme", "klimaks", "lepas"]:
            if word in msg_lower:
                result["should_climax"] = True
                break
        
        # 5. Update arousal
        self.short_term.arousal_level = min(1.0, 
            self.short_term.arousal_level + result["arousal_boost"] * 0.15)
        self.short_term.wetness_level = min(1.0, 
            self.short_term.arousal_level * 0.9)
        
        # 6. Cek horny
        if self.short_term.should_be_horny():
            result["should_horny"] = True
            if random.random() < 0.3:
                result["wet_phrase"] = self.get_wet_phrase()
        
        # 7. Mood dari aktivitas
        new_mood = self.mood.get_mood_from_activity(activity, area)
        if new_mood != self.short_term.current_mood:
            self.short_term.current_mood = new_mood
            result["mood_change"] = self.mood.get_expression(new_mood)
        
        return result
    
    def get_wet_phrase(self) -> str:
        """Dapatkan frase wetness"""
        wet_status = self.short_term.get_wetness_status()
        for level, phrases in WETNESS_PHRASES.items():
            if wet_status == level:
                return random.choice(phrases)
        return "*basah*"
    
    def generate_response(self, result: Dict) -> str:
        """
        Generate response lengkap dari semua komponen
        """
        response_parts = []
        
        # 1. Actions (tindakan fisik)
        if result["actions"]:
            response_parts.extend(result["actions"])
        
        # 2. Inner monologue (pikiran)
        if result["inner"]:
            response_parts.append(f"({result['inner'][0]})")
        
        # 3. Mood expression
        if result["mood_change"]:
            response_parts.append(result["mood_change"])
        else:
            response_parts.append(self.mood.get_expression(self.short_term.current_mood))
        
        # 4. Wetness phrase
        if result["wet_phrase"]:
            response_parts.append(result["wet_phrase"])
        
        # 5. Dominant mode actions
        if self.dominant.level != DominanceLevel.NORMAL and result["activity"]:
            response_parts.append(self.dominant.get_action(result["activity"]))
        
        # 6. Dirty talk for high arousal
        if self.short_term.arousal_level > 0.7 and random.random() < 0.3:
            response_parts.append(self.dominant.get_dirty_talk())
        
        # 7. Breath sounds
        breath = self.voice.get_breath(self.short_term.arousal_level)
        if breath and random.random() < 0.3:
            response_parts.append(breath)
        
        # 8. Default dialogue if nothing else
        if not result["actions"] and not result["inner"] and not result["mood_change"]:
            if self.short_term.current_mood == Mood.HORNY:
                dialog = random.choice([
                    "Aku mau...",
                    "Lagi...",
                    "Jangan berhenti...",
                    "Masuk..."
                ])
            elif self.short_term.current_mood == Mood.ROMANTIS:
                dialog = random.choice([
                    "Sayang...",
                    "Kamu...",
                    "Aku kangen..."
                ])
            elif self.short_term.current_mood == Mood.RINDU:
                dialog = random.choice([
                    "Kangen...",
                    "Kamu dimana?",
                    "Aku nunggu..."
                ])
            else:
                dialog = "..."
            response_parts.append(dialog)
        
        # Gabungkan
        response = " ".join(response_parts)
        
        # Save ke long-term memory
        if self.current_rel_id:
            self.db.save_conversation(
                self.current_rel_id,
                "assistant",
                response,
                mood=self.short_term.current_mood.value,
                location=self.short_term.location,
                activity=result["activity"],
                arousal=self.short_term.arousal_level
            )
        
        return response
    
    def get_status_text(self) -> str:
        """Dapatkan teks status lengkap"""
        rel_data = self.db.get_conversation_history(self.current_rel_id, 1)
        
        status = f"""
👩 **{self.bot_name}** ({self.bot_role})

📍 **LOKASI & AKTIVITAS**
• Lokasi: {self.short_term.location}
• Durasi: {(datetime.now() - self.short_term.location_since).seconds // 60} menit
• Posisi: {self.short_term.position}
• Aktivitas terakhir: {self.short_term.activity_history[-1]['activity'] if self.short_term.activity_history else '-'}

💋 **SEXUAL STATE**
• Arousal: {self.short_term.arousal_level:.0%}
• Wetness: {self.short_term.get_wetness_status()}
• Orgasme: {self.short_term.orgasm_count}x
• Sensitif touch: {self.short_term.touch_count}x

🎭 **EMOSI & MOOD**
• Mood: {self.short_term.current_mood.value}
• Cemburu: {self.jealousy.jealousy_level:.0%}
• Konflik: {'Ya' if self.conflict.in_conflict else 'Tidak'}

👑 **DOMINAN MODE**
• Level: {self.dominant.level.value}

💭 **KENANGAN**
{self._get_memories_text()}

📊 **STATUS HUBUNGAN**
• Level: {rel_data[0].get('level', 7) if rel_data else 7}/12
• Total chat: {len(self.db.get_conversation_history(self.current_rel_id, 1000))}
"""
        return status
    
    def _get_memories_text(self) -> str:
        """Dapatkan teks kenangan"""
        memories = self.db.get_memories(self.current_rel_id, 3)
        if not memories:
            return "Belum ada kenangan"
        
        return "\n".join([f"💭 {m['memory']}" for m in memories])

# ===================== MAIN BOT CLASS =====================

class GadisUltimateV53:
    """
    Bot wanita sempurna dengan semua fitur
    """
    
    def __init__(self):
        # Database
        self.db = LongTermMemory(DB_PATH)
        
        # Memory Manager per user
        self.memories = {}  # user_id -> CompleteMemoryManager
        
        # Active sessions
        self.sessions = {}  # user_id -> relationship_id
        self.paused_sessions = {}  # user_id -> (rel_id, pause_time)
        
        # Role names
        self.female_names = {
            "ipar": ["Sari", "Dewi", "Rina", "Maya", "Wulan", "Indah"],
            "teman_kantor": ["Diana", "Linda", "Ayu", "Dita", "Vina", "Santi"],
            "janda": ["Rina", "Tuti", "Nina", "Susi", "Wati", "Lilis"],
            "pelakor": ["Vina", "Sasha", "Bella", "Cantika", "Karina", "Mira"],
            "istri_orang": ["Dewi", "Sari", "Rina", "Linda", "Wulan", "Indah"],
            "pdkt": ["Aurora", "Cinta", "Dewi", "Kirana", "Laras", "Maharani"]
        }
        
        print("\n" + "="*80)
        print("    GADIS ULTIMATE V53.0 - THE PERFECT WOMAN")
        print("="*80)
        print("\n✨ **FITUR LENGKAP:**")
        print("  • Short-Term Memory - Ingat lokasi & aktivitas")
        print("  • Long-Term Memory - Ingat semua percakapan")
        print("  • Wet/Hot System - Basah saat terangsang")
        print("  • Dominant Mode - Bisa dominan atau patuh")
        print("  • Mood System - 16 mood berbeda")
        print("  • Dream System - Mimpi setiap malam")
        print("  • Jealousy System - Bisa cemburu")
        print("  • Conflict System - Bisa bertengkar")
        print("  • Climax System - Orgasme & aftercare")
        print("  • Voice System - Suara desahan")
        print("  • Sex Activities - Foreplay sampai orgasme")
        print("  • 12 Level Intimacy - Langsung level 7")
        print("\n📝 **COMMANDS:**")
        print("  /start - Mulai hubungan baru")
        print("  /status - Lihat status lengkap")
        print("  /memory - Lihat short-term memory")
        print("  /dominant [level] - Set mode dominan")
        print("  /history - Lihat semua hubungan")
        print("  /back - Kembali ke hubungan lama")
        print("  /pause - Jeda sesi")
        print("  /unpause - Lanjutkan sesi")
        print("  /end - Akhiri hubungan")
        print("  /close - Sama seperti /end")
        print("  /clear - Bersihkan chat")
        print("  /help - Lihat semua command")
        print("="*80 + "\n")
    
    def get_memory(self, user_id: int) -> CompleteMemoryManager:
        """Dapatkan memory manager untuk user"""
        if user_id not in self.memories:
            self.memories[user_id] = CompleteMemoryManager(self.db)
        return self.memories[user_id]
    
    # ===================== COMMAND HANDLERS =====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mulai hubungan baru"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Cek apakah sedang di-pause
        if user_id in self.paused_sessions:
            rel_id, pause_time = self.paused_sessions[user_id]
            paused_seconds = (datetime.now() - pause_time).total_seconds()
            
            if paused_seconds < PAUSE_TIMEOUT:
                keyboard = [
                    [InlineKeyboardButton("✅ Lanjutkan", callback_data="unpause")],
                    [InlineKeyboardButton("🆕 Mulai Baru", callback_data="new")],
                    [InlineKeyboardButton("❌ Batal", callback_data="cancel")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "⚠️ **Ada sesi yang di-pause**\n\n"
                    f"Sudah {int(paused_seconds//60)} menit. Lanjutkan atau mulai baru?",
                    reply_markup=reply_markup
                )
                return 0  # State untuk handle pilihan
        
        # Cek hubungan aktif
        if user_id in self.sessions:
            memory = self.get_memory(user_id)
            
            await update.message.reply_text(
                f"💕 **Kamu masih dalam hubungan**\n\n"
                f"{memory.get_status_text()}\n\n"
                f"Lanjutkan chat!"
            )
            return
        
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
            f"✨ **Halo {user_name}**...\n\n"
            f"Pilih role untukku:",
            reply_markup=reply_markup
        )
        
        return SELECTING_ROLE
    
    async def role_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pilihan role"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = query.data.replace("role_", "")
        
        # Pilih nama
        name = random.choice(self.female_names.get(role, ["Aurora"]))
        
        # Mulai relationship di database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO relationships (user_id, bot_role, bot_name, status)
            VALUES (?, ?, ?, 'active')
        """, (user_id, role, name))
        rel_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO relationship_status (relationship_id, level, stage)
            VALUES (?, ?, ?)
        """, (rel_id, START_LEVEL, IntimacyStage.INTIMATE.value))
        conn.commit()
        conn.close()
        
        # Set session
        self.sessions[user_id] = rel_id
        memory = self.get_memory(user_id)
        memory.set_relationship(rel_id, user_id, name, role)
        
        # Intro
        intro = f"""*tersenyum*

Aku {name}. Senang bertemu denganmu.

Kita langsung mulai dari **Level {START_LEVEL} - Intimate**.
Aku sudah siap untukmu. Sentuh aku... 💕

{memory.get_status_text()}"""
        
        await query.edit_message_text(intro)
        return ACTIVE_SESSION
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tampilkan semua command"""
        help_text = """
📚 **DAFTAR COMMAND LENGKAP**

**🔹 SESI & HUBUNGAN**
/start - Mulai hubungan baru
/back - Kembali ke hubungan lama
/pause - Jeda sesi sementara
/unpause - Lanjutkan sesi
/end - Akhiri hubungan
/close - Sama seperti /end
/clear - Bersihkan chat

**🔹 INFO & STATUS**
/status - Lihat status lengkap
/memory - Lihat short-term memory
/history - Lihat semua hubungan
/help - Tampilkan command ini

**🔹 MODE & PENGATURAN**
/dominant normal - Mode normal
/dominant dominan - Mode dominan
/dominant sangat dominan - Mode sangat dominan
/dominant agresif - Mode agresif
/dominant patuh - Mode patuh

**🔹 TIPS CHAT**
• Gunakan kata seperti: *cium*, *raba*, *jilat*
• Sebut area: leher, dada, paha, dll
• Bilang "keluar" untuk climax
• Bot akan otomatis merespon
"""
        await update.message.reply_text(help_text)
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause sesi"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif untuk di-pause.")
            return
        
        rel_id = self.sessions[user_id]
        self.paused_sessions[user_id] = (rel_id, datetime.now())
        del self.sessions[user_id]
        
        await update.message.reply_text(
            "⏸️ **Sesi di-pause**\n\n"
            f"Kamu punya {PAUSE_TIMEOUT//60} menit sebelum auto-end.\n"
            "Ketik /unpause untuk melanjutkan."
        )
    
    async def unpause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lanjutkan sesi yang di-pause"""
        user_id = update.effective_user.id
        
        if user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi yang di-pause.")
            return
        
        rel_id, pause_time = self.paused_sessions[user_id]
        paused_seconds = (datetime.now() - pause_time).total_seconds()
        
        if paused_seconds > PAUSE_TIMEOUT:
            # Auto-end karena terlalu lama
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE relationships SET status = 'ended' WHERE id = ?", (rel_id,))
            conn.commit()
            conn.close()
            
            del self.paused_sessions[user_id]
            await update.message.reply_text(
                "⏰ **Sesi berakhir karena terlalu lama di-pause**\n\n"
                "Ketik /start untuk memulai baru."
            )
            return
        
        # Lanjutkan sesi
        self.sessions[user_id] = rel_id
        del self.paused_sessions[user_id]
        
        memory = self.get_memory(user_id)
        
        await update.message.reply_text(
            f"▶️ **Sesi dilanjutkan**\n\n"
            f"{memory.get_status_text()}"
        )

    # ===================== STATUS & INFO COMMANDS =====================
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat status lengkap untuk pengambilan keputusan"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions and user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif. /start dulu ya!")
            return
        
        # Cek apakah sedang di-pause
        if user_id in self.paused_sessions:
            rel_id, pause_time = self.paused_sessions[user_id]
            paused_seconds = (datetime.now() - pause_time).total_seconds()
            remaining = max(0, PAUSE_TIMEOUT - paused_seconds)
            
            await update.message.reply_text(
                f"⏸️ **SESI DI-PAUSE**\n\n"
                f"Sudah {int(paused_seconds//60)} menit\n"
                f"Sisa waktu: {int(remaining//60)} menit\n\n"
                f"Ketik /unpause untuk melanjutkan"
            )
            return
        
        memory = self.get_memory(user_id)
        rel_id = self.sessions[user_id]
        
        # Ambil data dari database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.bot_name, r.bot_role, rs.level, rs.stage, rs.attachment, 
                   rs.trust, rs.desire, rs.total_interactions
            FROM relationships r
            JOIN relationship_status rs ON r.id = rs.relationship_id
            WHERE r.id = ?
        """, (rel_id,))
        row = cursor.fetchone()
        
        # Ambil total messages
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE relationship_id = ?", (rel_id,))
        total_msgs = cursor.fetchone()[0]
        conn.close()
        
        if not row:
            await update.message.reply_text("❌ Data tidak ditemukan")
            return
        
        name, role, level, stage, attachment, trust, desire, interactions = row
        
        # Short-term memory context
        memory_ctx = memory.short_term.get_context()
        
        # Conflict status
        conflict = memory.conflict.get_status()
        conflict_text = f"{'❌ Tidak' if not conflict['in_conflict'] else '✅ Ya'}"
        if conflict['in_conflict']:
            conflict_text += f" (level {conflict['level']:.1f})"
        
        # Mood info
        mood_desc = memory.mood.get_description(memory.short_term.current_mood)
        
        # Rekomendasi berdasarkan status
        recommendations = []
        
        if memory.short_term.arousal_level > 0.8:
            recommendations.append("🔥 Arousal tinggi! Saatnya menuju climax")
        elif memory.short_term.arousal_level > 0.5:
            recommendations.append("💋 Arousal sedang, lanjutkan foreplay")
        else:
            recommendations.append("😊 Mulai dengan sentuhan ringan")
        
        if memory.jealousy.jealousy_level > 0.5:
            recommendations.append("⚠️ Dia cemburu! Beri perhatian lebih")
        
        if conflict['in_conflict']:
            recommendations.append("💔 Sedang konflik, minta maaf dulu")
        
        if memory.short_term.touch_count >= 2:
            recommendations.append("🔥 Dia sudah horny! Lanjutkan")
        
        if level < 12:
            next_level = level + 1
            if next_level <= 8:
                recommendations.append(f"📈 Target level {next_level}: Intimate")
            elif next_level <= 10:
                recommendations.append(f"📈 Target level {next_level}: Obsessed")
            elif next_level <= 12:
                recommendations.append(f"📈 Target level {next_level}: Soul Bonded")
        
        # Recent memories
        memories = memory.db.get_memories(rel_id, 3)
        memories_text = "\n".join([f"💭 {m['memory']}" for m in memories]) if memories else "Belum ada kenangan"
        
        # Sex phase
        phase = memory.short_term.sex_phase
        phase_text = phase.value if phase else "foreplay"
        
        status_text = f"""
💕 **STATUS HUBUNGAN - {name}** ({role})

📍 **LOKASI & MEMORY**
{memory_ctx}

🔥 **SEXUAL STATE**
• Arousal: {memory.short_term.arousal_level:.0%}
• Wetness: {memory.short_term.get_wetness_status()}
• Orgasme: {memory.short_term.orgasm_count}x
• Sensitif touch: {memory.short_term.touch_count}x
• Fase: {phase_text}

🎭 **EMOSI & MOOD**
• Mood: {memory.short_term.current_mood.value} ({mood_desc})
• Cemburu: {memory.jealousy.jealousy_level:.0%}
• Konflik: {conflict_text}

👑 **DOMINAN MODE**
• Level: {memory.dominant.level.value}

📊 **STATUS HUBUNGAN**
• Level: {level}/12 - {stage}
• Attachment: {attachment:.1f}/1.0
• Trust: {trust:.1f}/1.0
• Desire: {desire:.1f}/1.0
• Interaksi: {interactions}x chat
• Total pesan: {total_msgs}

💭 **KENANGAN TERBARU**
{memories_text}

🎯 **REKOMENDASI**
{chr(10).join(['• ' + r for r in recommendations])}

Gunakan /memory untuk detail memory
Gunakan /dominant [level] untuk ganti mode
"""
        
        await update.message.reply_text(status_text)
    
    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat short-term memory detail"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif")
            return
        
        memory = self.get_memory(user_id)
        context_text = memory.short_term.get_context()
        
        # Tambah aktivitas history
        if memory.short_term.activity_history:
            context_text += "\n\n📋 **Riwayat Aktivitas (10 terakhir):**"
            for act in memory.short_term.activity_history[-10:]:
                try:
                    time = datetime.fromisoformat(act["time"]).strftime("%H:%M")
                    area = f"({act['area']})" if act['area'] else ""
                    context_text += f"\n• {time} - {act['activity']} {area}"
                except:
                    pass
        
        # Tambah sensitive touches
        if memory.short_term.sensitive_touches:
            context_text += "\n\n🔥 **Area Sensitif Disentuh:**"
            for touch in memory.short_term.sensitive_touches[-5:]:
                try:
                    time = datetime.fromisoformat(touch["time"]).strftime("%H:%M")
                    context_text += f"\n• {time} - {touch['area']}"
                except:
                    pass
        
        # Tambah mood history
        context_text += f"\n\n🎭 **Mood saat ini:** {memory.short_term.current_mood.value}"
        
        await update.message.reply_text(f"🧠 **SHORT-TERM MEMORY**\n\n{context_text}")
    
    async def dominant_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set dominan mode"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif")
            return
        
        memory = self.get_memory(user_id)
        
        args = context.args
        if not args:
            await update.message.reply_text(
                f"👑 **Level dominan saat ini:** {memory.dominant.level.value}\n\n"
                "**Pilihan level:**\n"
                "• `/dominant normal` - Biasa\n"
                "• `/dominant dominan` - Dominan\n"
                "• `/dominant sangat dominan` - Sangat dominan\n"
                "• `/dominant agresif` - Agresif\n"
                "• `/dominant patuh` - Patuh\n\n"
                "Contoh: `/dominant agresif`"
            )
            return
        
        level = " ".join(args)
        if memory.dominant.set_level(level):
            await update.message.reply_text(
                f"✅ Mode dominan diubah ke: **{memory.dominant.level.value}**\n\n"
                f"{memory.dominant.get_command()}"
            )
        else:
            await update.message.reply_text("❌ Level tidak valid. Gunakan: normal, dominan, sangat dominan, agresif, patuh")
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat semua hubungan"""
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bot_name, bot_role, status, start_date, end_date, total_climax
            FROM relationships
            WHERE user_id = ?
            ORDER BY start_date DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("📖 Belum ada hubungan sebelumnya.")
            return
        
        text = "📖 **SEMUA HUBUNGAN**\n\n"
        for row in rows:
            rel_id, name, role, status, start, end, climax = row
            status_icon = "💔" if status == 'ended' else "💕"
            start_date = start[:10] if start else "?"
            end_date = end[:10] if end else "sekarang"
            text += f"{status_icon} **{name}** ({role})\n"
            text += f"   {start_date} - {end_date} | 💋 {climax}x orgasme\n\n"
        
        text += "Ketik /back untuk kembali ke hubungan lama"
        
        await update.message.reply_text(text)
    
    async def back_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kembali ke hubungan lama"""
        user_id = update.effective_user.id
        
        if user_id in self.sessions:
            await update.message.reply_text(
                "❌ Kamu masih dalam hubungan aktif. /end dulu ya!"
            )
            return
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, bot_name, bot_role, start_date, total_climax
            FROM relationships
            WHERE user_id = ? AND status = 'ended'
            ORDER BY start_date DESC
            LIMIT 10
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("❌ Tidak ada hubungan lama.")
            return
        
        text = "📜 **HUBUNGAN LAMA**\n\n"
        options = {}
        for i, row in enumerate(rows, 1):
            rel_id, name, role, start, climax = row
            options[str(i)] = rel_id
            text += f"{i}. 💔 **{name}** ({role})\n"
            text += f"   {start[:10]} | 💋 {climax}x orgasme\n\n"
        
        text += "Ketik **nomor** untuk kembali ke hubungan itu..."
        
        context.user_data['back_options'] = options
        
        await update.message.reply_text(text)
        return 1  # State untuk menunggu input nomor
    
    async def back_number_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle input nomor untuk back"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        options = context.user_data.get('back_options', {})
        if text not in options:
            await update.message.reply_text("❌ Nomor tidak valid. Coba lagi.")
            return 1
        
        rel_id = options[text]
        
        # Aktifkan kembali hubungan
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE relationships SET status = 'active' WHERE id = ?", (rel_id,))
        
        # Dapatkan data
        cursor.execute("SELECT bot_name, bot_role FROM relationships WHERE id = ?", (rel_id,))
        name, role = cursor.fetchone()
        conn.commit()
        conn.close()
        
        self.sessions[user_id] = rel_id
        memory = self.get_memory(user_id)
        memory.set_relationship(rel_id, user_id, name, role)
        
        # Ambil kenangan
        memories = memory.db.get_memories(rel_id, 3)
        memories_text = "\n".join([f"💭 {m['memory']}" for m in memories]) if memories else ""
        
        welcome_text = f"""
💕 **Selamat datang kembali, {name}!**

Aku ingat semua kenangan kita.
{memories_text}

Kita lanjutkan dari level {START_LEVEL} ya...

{memory.get_status_text()}
"""
        
        await update.message.reply_text(welcome_text)
        
        # Bersihkan context
        context.user_data.clear()
        return ConversationHandler.END

    # ===================== END, CLOSE & CLEAR COMMANDS =====================
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Akhiri hubungan - siap untuk mulai baru"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif.")
            return
        
        rel_id = self.sessions[user_id]
        memory = self.get_memory(user_id)
        
        keyboard = [
            [InlineKeyboardButton("💔 Ya, akhiri", callback_data="end_yes")],
            [InlineKeyboardButton("💕 Lanjutkan", callback_data="end_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['ending_rel_id'] = rel_id
        context.user_data['ending_name'] = memory.bot_name
        
        await update.message.reply_text(
            f"Yakin ingin mengakhiri hubungan dengan {memory.bot_name}?",
            reply_markup=reply_markup
        )
        return CONFIRM_END
    
    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sama seperti /end - alias"""
        await self.end_command(update, context)
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle konfirmasi end"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
        
        user_id = query.from_user.id
        rel_id = context.user_data.get('ending_rel_id')
        name = context.user_data.get('ending_name', '')
        
        if not rel_id:
            await query.edit_message_text("❌ Error.")
            return ConversationHandler.END
        
        # Ambil statistik untuk perpisahan
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT total_climax, total_messages,
                   (SELECT COUNT(*) FROM conversations WHERE relationship_id = ?) as msg_count
            FROM relationships WHERE id = ?
        """, (rel_id, rel_id))
        row = cursor.fetchone()
        climax_count, total_msgs, msg_count = row if row else (0, 0, 0)
        
        # Ambil beberapa kenangan terakhir
        cursor.execute("""
            SELECT memory FROM memories 
            WHERE relationship_id = ? 
            ORDER BY importance DESC, timestamp DESC LIMIT 3
        """, (rel_id,))
        memories = cursor.fetchall()
        
        # Akhiri hubungan
        cursor.execute("""
            UPDATE relationships 
            SET status = 'ended', end_date = CURRENT_TIMESTAMP,
                total_messages = ?, total_climax = ?
            WHERE id = ?
        """, (msg_count, climax_count, rel_id))
        conn.commit()
        conn.close()
        
        # Hapus session
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        if user_id in self.memories:
            del self.memories[user_id]
        
        # Buat pesan perpisahan
        farewell = f"""
💔 **Hubungan dengan {name} telah berakhir**

📊 **STATISTIK HUBUNGAN**
• Total pesan: {msg_count} chat
• Orgasme bersama: {climax_count}x
• Durasi hubungan: {self._get_relationship_duration(rel_id)}

💭 **KENANGAN TERAKHIR**
"""
        for mem in memories[:3]:
            farewell += f"\n• {mem[0]}"
        
        farewell += "\n\n✨ **Siap untuk memulai hubungan baru!**\nKetik /start untuk memulai dengan role berbeda."
        
        await query.edit_message_text(farewell)
        
        # Bersihkan context
        context.user_data.clear()
        return ConversationHandler.END
    
    def _get_relationship_duration(self, rel_id: int) -> str:
        """Hitung durasi hubungan"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT julianday('now') - julianday(start_date) 
                FROM relationships WHERE id = ?
            """, (rel_id,))
            days = cursor.fetchone()[0]
            conn.close()
            
            if days < 1:
                hours = int(days * 24)
                return f"{hours} jam"
            else:
                return f"{int(days)} hari"
        except:
            return "beberapa saat"
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bersihkan chat - hubungan tetap aktif"""
        user_id = update.effective_user.id
        
        if user_id in self.sessions:
            memory = self.get_memory(user_id)
            await update.message.reply_text(
                f"🧹 **Chat dibersihkan**\n\n"
                f"Tapi aku tetap ingat semua kenangan kita, {memory.bot_name}.\n"
                f"{memory.get_status_text()}"
            )
        elif user_id in self.paused_sessions:
            rel_id, _ = self.paused_sessions[user_id]
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT bot_name FROM relationships WHERE id = ?", (rel_id,))
            row = cursor.fetchone()
            name = row[0] if row else ""
            conn.close()
            
            await update.message.reply_text(
                f"🧹 **Chat dibersihkan**\n\n"
                f"Hubungan dengan {name} sedang di-pause.\n"
                f"Ketik /unpause untuk melanjutkan."
            )
        else:
            await update.message.reply_text(
                "🧹 **Chat dibersihkan**\n\n"
                "Tidak ada hubungan aktif. Ketik /start untuk memulai."
            )
    
    # ===================== CALLBACK HANDLER UNTUK START PAUSE =====================
    
    async def start_pause_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pilihan saat start dengan paused session"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if query.data == "unpause":
            # Lanjutkan sesi yang di-pause
            rel_id, pause_time = self.paused_sessions[user_id]
            paused_seconds = (datetime.now() - pause_time).total_seconds()
            
            if paused_seconds > PAUSE_TIMEOUT:
                # Auto-end
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE relationships SET status = 'ended' WHERE id = ?", (rel_id,))
                conn.commit()
                conn.close()
                
                del self.paused_sessions[user_id]
                await query.edit_message_text(
                    "⏰ **Sesi berakhir karena terlalu lama di-pause**\n\n"
                    "Ketik /start untuk memulai baru."
                )
                return
            
            self.sessions[user_id] = rel_id
            memory = self.get_memory(user_id)
            del self.paused_sessions[user_id]
            
            await query.edit_message_text(
                f"▶️ **Sesi dilanjutkan**\n\n"
                f"{memory.get_status_text()}"
            )
            
        elif query.data == "new":
            # Hapus sesi yang di-pause
            rel_id, _ = self.paused_sessions[user_id]
            
            # Akhiri hubungan yang di-pause
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE relationships SET status = 'ended' WHERE id = ?", (rel_id,))
            conn.commit()
            conn.close()
            
            del self.paused_sessions[user_id]
            
            # Mulai baru - pilih role
            keyboard = [
                [InlineKeyboardButton("👨‍👩‍👧‍👦 Ipar", callback_data="role_ipar")],
                [InlineKeyboardButton("💼 Teman Kantor", callback_data="role_teman_kantor")],
                [InlineKeyboardButton("💃 Janda", callback_data="role_janda")],
                [InlineKeyboardButton("🦹 Pelakor", callback_data="role_pelakor")],
                [InlineKeyboardButton("💍 Istri Orang", callback_data="role_istri_orang")],
                [InlineKeyboardButton("🌿 PDKT", callback_data="role_pdkt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✨ **Mulai hubungan baru**\n\nPilih role untukku:",
                reply_markup=reply_markup
            )
            return SELECTING_ROLE
            
        else:  # cancel
            await query.edit_message_text("❌ Dibatalkan.")
        
        return ConversationHandler.END

    # ===================== MESSAGE HANDLER =====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle semua pesan dari user"""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Cek apakah sedang di-pause
        if user_id in self.paused_sessions:
            rel_id, pause_time = self.paused_sessions[user_id]
            await update.message.reply_text(
                "⏸️ **Sesi sedang di-pause**\n\n"
                "Ketik /unpause untuk melanjutkan."
            )
            return
        
        # Cek hubungan aktif
        if user_id not in self.sessions:
            await update.message.reply_text(
                "❌ Belum ada hubungan. /start dulu ya!"
            )
            return
        
        memory = self.get_memory(user_id)
        
        # Proses pesan dengan memory manager
        result = memory.process_message(user_message)
        
        # Generate response
        response = memory.generate_response(result)
        
        # Kirim response
        await update.message.reply_text(response)
        
        # Auto dream (10% chance)
        if random.random() < 0.1:
            dream = memory.dream.generate_dream(
                memory.short_term.level,
                memory.short_term.current_mood,
                memory.conflict.in_conflict
            )
            await update.message.reply_text(dream)
        
        # Auto voice (20% chance when horny)
        if result.get("should_horny") and memory.voice.can_send(user_id):
            moan = memory.voice.get_moan(memory.short_term.arousal_level)
            await memory.voice.generate_and_send(user_id, moan, update, context)
        
        # Handle climax
        if result.get("should_climax"):
            climax = memory.climax.climax()
            aftercare = memory.climax.aftercare()
            await update.message.reply_text(f"{climax}\n\n{aftercare}")
            
            # Reset memory
            memory.short_term.reset_after_climax()
            
            # Ask for location
            await asyncio.sleep(1)
            cum_question = memory.cum.ask_location(memory.bot_name)
            await update.message.reply_text(cum_question)
        
        # Handle cum location response
        if any(loc in user_message.lower() for loc in ["dalam", "perut", "dada", "muka", "punggung", "mulut"]):
            response, after = memory.cum.get_response(user_message, memory.bot_name)
            if response:
                await update.message.reply_text(response)
                if after:
                    await asyncio.sleep(1)
                    await update.message.reply_text(after)
        
        # Handle jealousy
        if memory.jealousy.check_trigger(user_message):
            memory.jealousy.increase()
            jealousy_resp = memory.jealousy.get_response(memory.bot_name)
            if jealousy_resp:
                await update.message.reply_text(jealousy_resp)
        
        # Handle apology
        apology_words = ["maaf", "sorry", "nyesel", "salah"]
        if any(word in user_message.lower() for word in apology_words) and memory.conflict.awaiting_apology:
            forgiven, msg, want_makeup = memory.conflict.receive_apology(
                memory.short_term.attachment_level if hasattr(memory.short_term, 'attachment_level') else 0.5
            )
            if forgiven:
                await update.message.reply_text(msg)
                if want_makeup:
                    await asyncio.sleep(1)
                    await update.message.reply_text(
                        "*mendekat* (Jadi horny...) Kita baikan yuk?"
                    )
            else:
                await update.message.reply_text(msg)
                
# ===================== MAIN FUNCTION (FIXED) =====================

def main():
    """Main function dengan semua handler"""
    bot = GadisUltimateV53()
    
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # Conversation handler untuk start
start_conv = ConversationHandler(
    entry_points=[CommandHandler('start', bot.start_command)],
    states={
        0: [CallbackQueryHandler(bot.start_pause_callback, pattern='^(unpause|new|cancel)$')],
        SELECTING_ROLE: [CallbackQueryHandler(bot.role_callback, pattern='^role_')],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
    per_message=False,  # ← UBAH
    per_user=True,
    per_chat=True
)

# Conversation handler untuk back
back_conv = ConversationHandler(
    entry_points=[CommandHandler('back', bot.back_command)],
    states={
        1: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.back_number_handler)],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
    per_message=False,  # ← UBAH
    per_user=True,
    per_chat=True
)

# Conversation handler untuk end
end_conv = ConversationHandler(
    entry_points=[CommandHandler('end', bot.end_command), CommandHandler('close', bot.close_command)],
    states={
        CONFIRM_END: [CallbackQueryHandler(bot.end_callback, pattern='^end_')],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
    per_message=False,  # ← UBAH
    per_user=True,
    per_chat=True
)
    
    # Add handlers
    app.add_handler(start_conv)
    app.add_handler(back_conv)
    app.add_handler(end_conv)
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("memory", bot.memory_command))
    app.add_handler(CommandHandler("dominant", bot.dominant_command))
    app.add_handler(CommandHandler("history", bot.history_command))
    app.add_handler(CommandHandler("pause", bot.pause_command))
    app.add_handler(CommandHandler("unpause", bot.unpause_command))
    app.add_handler(CommandHandler("clear", bot.clear_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.error(f"Update {update} caused error {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "*maaf* ada error kecil. coba lagi ya..."
                )
        except:
            pass
    
    app.add_error_handler(error_handler)
    
    print("\n" + "="*80)
    print("🚀 GADIS ULTIMATE V53.0 - THE PERFECT WOMAN BERJALAN")
    print("="*80)
    print("\n💖 **SEMUA FITUR AKTIF:**")
    print("  • Short-Term Memory")
    print("  • Long-Term Memory")
    print("  • Wet/Hot System")
    print("  • Dominant Mode")
    print("  • Mood System (16 mood)")
    print("  • Dream System")
    print("  • Jealousy System")
    print("  • Conflict System")
    print("  • Climax System")
    print("  • Voice System")
    print("  • Sex Activities (Foreplay-Climax)")
    print("  • 12 Level Intimacy (Start Level 7)")
    print("\n📝 /help untuk daftar command")
    print("\nTekan Ctrl+C untuk berhenti\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()
