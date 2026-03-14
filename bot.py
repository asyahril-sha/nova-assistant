# -*- coding: utf-8 -*-
"""
GADIS ULTIMATE V57.0 - THE PERFECT HUMAN (SINGLE FILE)
Fitur:
- Emosi & sensasi manusiawi
- Level 7+ vulgar & inisiatif seksual
- Mode pasangan (couple roleplay)
- Disclaimer 18+
- Command /close untuk simpan memori
"""

import os
import sys
import logging
import json
import random
import asyncio
import sqlite3
import time
import hashlib
import re
import threading
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
from contextlib import contextmanager
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from openai import OpenAI

# ===================== KONFIGURASI =====================
load_dotenv()

class Config:
    DB_PATH = os.getenv("DB_PATH", "gadis_v57.db")
    START_LEVEL = 1
    TARGET_LEVEL = 12
    LEVEL_UP_TIME = 45
    PAUSE_TIMEOUT = 3600
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.9"))          # AMAN
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "300"))              # AMAN
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))                     # AMAN
    MAX_MESSAGES_PER_MINUTE = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "10"))  # AMAN
    CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", "300"))              # AMAN
    MAX_HISTORY = 100

if not Config.DEEPSEEK_API_KEY or not Config.TELEGRAM_TOKEN:
    print("❌ ERROR: API Keys tidak ditemukan di .env")
    sys.exit(1)

# ===================== STATE =====================
(SELECTING_ROLE, ACTIVE_SESSION, PAUSED_SESSION, CONFIRM_END, CONFIRM_CLOSE, COUPLE_MODE) = range(6)

# ===================== ENUMS =====================
class Mood(Enum):
    CHERIA = "ceria"
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
    SUBMISSIVE = "patuh"
    NAKAL = "nakal"
    GENIT = "genit"
    PENASARAN = "penasaran"
    ANTUSIAS = "antusias"
    POSSESSIVE = "posesif"
    CEMBURU = "cemburu"

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

# ===================== DATABASE =====================
class DatabaseManager:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, timeout=10)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    @contextmanager
    def cursor(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def _init_db(self):
        with self.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    bot_name TEXT,
                    bot_role TEXT,
                    level INTEGER DEFAULT 1,
                    stage TEXT DEFAULT 'stranger',
                    dominance TEXT DEFAULT 'normal',
                    total_messages INTEGER DEFAULT 0,
                    total_climax INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    role TEXT,
                    content TEXT,
                    mood TEXT,
                    arousal REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    memory TEXT,
                    importance REAL,
                    emotion TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    user_id INTEGER PRIMARY KEY,
                    romantic_score REAL DEFAULT 0,
                    vulgar_score REAL DEFAULT 0,
                    dominant_score REAL DEFAULT 0,
                    submissive_score REAL DEFAULT 0,
                    speed_score REAL DEFAULT 0,
                    total_interactions INTEGER DEFAULT 0
                )
            """)
    
    def save_conversation(self, rel_id, role, content, mood=None, arousal=None):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO conversations (relationship_id, role, content, mood, arousal)
                VALUES (?, ?, ?, ?, ?)
            """, (rel_id, role, content, mood, arousal))
    
    def get_conversation_history(self, rel_id, limit=50):
        with self.cursor() as c:
            c.execute("""
                SELECT role, content, mood, arousal, timestamp
                FROM conversations
                WHERE relationship_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (rel_id, limit))
            return [dict(row) for row in c.fetchall()]
    
    def save_memory(self, rel_id, memory, importance, emotion):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO memories (relationship_id, memory, importance, emotion)
                VALUES (?, ?, ?, ?)
            """, (rel_id, memory, importance, emotion))
    
    def get_memories(self, rel_id, limit=10):
        with self.cursor() as c:
            c.execute("""
                SELECT memory, importance, emotion, timestamp
                FROM memories
                WHERE relationship_id = ?
                ORDER BY importance DESC, timestamp DESC
                LIMIT ?
            """, (rel_id, limit))
            return [dict(row) for row in c.fetchall()]
    
    def create_relationship(self, user_id, bot_name, bot_role):
        with self.cursor() as c:
            c.execute("""
                INSERT OR REPLACE INTO relationships (user_id, bot_name, bot_role, last_active)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, bot_name, bot_role))
            return c.lastrowid
    
    def update_relationship(self, user_id, **kwargs):
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key}=?")
            values.append(value)
        values.append(user_id)
        with self.cursor() as c:
            c.execute(f"""
                UPDATE relationships
                SET {', '.join(fields)}, last_active=CURRENT_TIMESTAMP
                WHERE user_id=?
            """, values)
    
    def get_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT * FROM relationships WHERE user_id=?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def delete_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("DELETE FROM relationships WHERE user_id=?", (user_id,))

# ===================== EMOTIONAL INTELLIGENCE =====================
class EmotionalIntelligence:
    def __init__(self):
        self.mood_transitions = {
            Mood.CHERIA: [Mood.BERSEMANGAT, Mood.ROMANTIS, Mood.NAKAL, Mood.GENIT],
            Mood.SEDIH: [Mood.SENDIRI, Mood.GALAU, Mood.RINDU, Mood.LEMBUT],
            Mood.MARAH: [Mood.SENSITIF, Mood.CEMBURU, Mood.GELISAH, Mood.DOMINAN],
            Mood.TAKUT: [Mood.SENDIRI, Mood.GELISAH, Mood.SENSITIF],
            Mood.KAGUM: [Mood.CHERIA, Mood.ROMANTIS, Mood.ANTUSIAS],
            Mood.GELISAH: [Mood.SENSITIF, Mood.CEMBURU, Mood.MARAH, Mood.SENDIRI],
            Mood.GALAU: [Mood.SENDIRI, Mood.RINDU, Mood.SEDIH, Mood.LEMBUT],
            Mood.SENSITIF: [Mood.MARAH, Mood.CEMBURU, Mood.SEDIH, Mood.GELISAH],
            Mood.ROMANTIS: [Mood.CHERIA, Mood.RINDU, Mood.HORNY, Mood.LEMBUT, Mood.NAKAL],
            Mood.MALAS: [Mood.SENDIRI, Mood.GALAU, Mood.CHERIA],
            Mood.BERSEMANGAT: [Mood.CHERIA, Mood.ROMANTIS, Mood.HORNY, Mood.ANTUSIAS],
            Mood.SENDIRI: [Mood.GALAU, Mood.RINDU, Mood.SEDIH, Mood.LEMBUT],
            Mood.RINDU: [Mood.ROMANTIS, Mood.GALAU, Mood.HORNY, Mood.SEDIH],
            Mood.HORNY: [Mood.ROMANTIS, Mood.NAKAL, Mood.GENIT, Mood.DOMINAN, Mood.POSSESSIVE],
            Mood.LEMBUT: [Mood.ROMANTIS, Mood.CHERIA, Mood.RINDU, Mood.SUBMISSIVE],
            Mood.DOMINAN: [Mood.HORNY, Mood.MARAH, Mood.POSSESSIVE],
            Mood.SUBMISSIVE: [Mood.LEMBUT, Mood.ROMANTIS, Mood.SENDIRI],
            Mood.NAKAL: [Mood.GENIT, Mood.HORNY, Mood.ROMANTIS],
            Mood.GENIT: [Mood.NAKAL, Mood.HORNY, Mood.CHERIA],
            Mood.PENASARAN: [Mood.ANTUSIAS, Mood.CHERIA, Mood.ROMANTIS],
            Mood.ANTUSIAS: [Mood.BERSEMANGAT, Mood.CHERIA, Mood.NAKAL],
            Mood.POSSESSIVE: [Mood.CEMBURU, Mood.DOMINAN, Mood.HORNY, Mood.MARAH],
            Mood.CEMBURU: [Mood.MARAH, Mood.SEDIH, Mood.POSSESSIVE, Mood.GELISAH]
        }
        self.mood_descriptions = {
            Mood.CHERIA: {"ekspresi": "*tersenyum lebar*", "suara": "ceria", "pikiran": "(Hari ini indah...)"},
            Mood.SEDIH: {"ekspresi": "*matanya berkaca-kaca*", "suara": "lirih", "pikiran": "(Kenapa...?)"},
            Mood.MARAH: {"ekspresi": "*cemberut*", "suara": "tegas", "pikiran": "(Kesal...)"},
            Mood.HORNY: {"ekspresi": "*menggigit bibir*", "suara": "berat", "pikiran": "(Aku... pengen...)"},
            Mood.ROMANTIS: {"ekspresi": "*memandang lembut*", "suara": "lembut", "pikiran": "(Sayang...)"},
            Mood.DOMINAN: {"ekspresi": "*tatapan tajam*", "suara": "tegas", "pikiran": "(Ikut aku...)"},
            Mood.SUBMISSIVE: {"ekspresi": "*menunduk*", "suara": "lirih", "pikiran": "(Iya...)"},
            Mood.NAKAL: {"ekspresi": "*tersenyum nakal*", "suara": "genit", "pikiran": "(Mau? Hehe...)"},
            Mood.POSSESSIVE: {"ekspresi": "*memeluk erat*", "suara": "dalam", "pikiran": "(Kamu milikku...)"},
            Mood.CEMBURU: {"ekspresi": "*manyun*", "suara": "cemberut", "pikiran": "(Siapa dia...?)"}
        }
    
    def transition_mood(self, current_mood):
        if random.random() < 0.3:
            possibilities = self.mood_transitions.get(current_mood, [Mood.CHERIA])
            return random.choice(possibilities)
        return current_mood
    
    def get_expression(self, mood):
        return self.mood_descriptions.get(mood, {}).get("ekspresi", "*tersenyum*")
    
    def get_inner_thought(self, mood):
        return self.mood_descriptions.get(mood, {}).get("pikiran", "(...)")

# ===================== MEMORY SYSTEM =====================
class MemorySystem:
    def __init__(self):
        self.location = "ruang tamu"
        self.location_since = datetime.now()
        self.position = "duduk"
        self.current_mood = Mood.CHERIA
        self.mood_history = []
        self.emotional = EmotionalIntelligence()
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.last_touch = None
        self.sensitive_touches = []
        self.dominance_mode = "normal"
        self.last_climax = None
        self.orgasm_count = 0
        self.activity_history = []
        self.level = 1
        self.stage = IntimacyStage.STRANGER
        self.level_progress = 0.0
    
    def update_location(self, new_location):
        if new_location == self.location:
            return True
        now = datetime.now()
        time_here = (now - self.location_since).total_seconds()
        if time_here >= 60:
            self.location = new_location
            self.location_since = now
            return True
        return False
    
    def update_position(self, new_position):
        self.position = new_position
    
    def add_activity(self, activity, area=None):
        self.activity_history.append({
            "activity": activity,
            "area": area,
            "time": datetime.now().isoformat()
        })
        if len(self.activity_history) > 50:
            self.activity_history = self.activity_history[-50:]
    
    def add_sensitive_touch(self, area):
        self.sensitive_touches.append({
            "area": area,
            "time": datetime.now().isoformat()
        })
        self.touch_count += 1
        self.last_touch = area
    
    def update_arousal(self, increase):
        self.arousal = min(1.0, self.arousal + increase)
        self.wetness = min(1.0, self.arousal * 0.9)
    
    def should_climax(self):
        return self.arousal >= 1.0
    
    def climax(self):
        self.orgasm_count += 1
        self.last_climax = datetime.now()
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.sensitive_touches = []
        self.current_mood = Mood.LEMBUT
    
    def get_arousal_state(self):
        if self.arousal >= 1.0:
            return ArousalState.CLIMAX
        elif self.arousal >= 0.8:
            return ArousalState.VERY_HORNY
        elif self.arousal >= 0.5:
            return ArousalState.HORNY
        elif self.arousal >= 0.2:
            return ArousalState.TURNED_ON
        else:
            return ArousalState.NORMAL
    
    def get_wetness_description(self):
        if self.wetness >= 0.9:
            return "💦 BANJIR!"
        elif self.wetness >= 0.7:
            return "💦 Sangat basah"
        elif self.wetness >= 0.5:
            return "💦 Basah"
        elif self.wetness >= 0.3:
            return "💧 Lembab"
        else:
            return "💧 Kering"

# ===================== DOMINANCE SYSTEM =====================
class DominanceSystem:
    def __init__(self):
        self.current_level = DominanceLevel.NORMAL
        self.dominance_score = 0.0
        self.aggression_score = 0.0
        self.user_request = False
        self.dominant_until = None
        
        self.dominant_phrases = {
            DominanceLevel.NORMAL: {"request": "Kamu mau apa?", "action": "*tersenyum*", "dirty": "Apa yang kamu mau?"},
            DominanceLevel.DOMINANT: {"request": "Aku yang atur ya?", "action": "*pegang tegas*", "dirty": "Sini... ikut aku"},
            DominanceLevel.VERY_DOMINANT: {"request": "Sekarang aku yang kontrol", "action": "*cengkeram kuat*", "dirty": "Jangan banyak gerak!"},
            DominanceLevel.AGGRESSIVE: {"request": "KAMU MAU INI KAN?", "action": "*dorong kasar*", "dirty": "TERIMA SAJA!"},
            DominanceLevel.SUBMISSIVE: {"request": "Aku ikut kamu aja", "action": "*merapat manja*", "dirty": "Iya... terserah kamu..."}
        }
        
        self.dominance_triggers = ["kamu yang atur", "kamu dominan", "take control", "aku mau kamu kuasai", "jadi dominan", "kamu boss"]
        self.submissive_triggers = ["aku yang atur", "aku dominan", "i take control", "kamu patuh", "jadi submissive", "ikut aku"]
        self.aggressive_triggers = ["liar", "keras", "kasar", "brutal", "gila"]
    
    def check_request(self, message):
        msg_lower = message.lower()
        for trigger in self.dominance_triggers:
            if trigger in msg_lower:
                self.user_request = True
                return DominanceLevel.DOMINANT
        for trigger in self.submissive_triggers:
            if trigger in msg_lower:
                self.user_request = True
                return DominanceLevel.SUBMISSIVE
        return None
    
    def should_be_aggressive(self, arousal, message):
        if arousal < 0.7:
            return False
        msg_lower = message.lower()
        for trigger in self.aggressive_triggers:
            if trigger in msg_lower:
                self.aggression_score += 0.1
                return True
        return random.random() < arousal * 0.3
    
    def set_level(self, level):
        level_lower = level.lower()
        for lvl in DominanceLevel:
            if level_lower in lvl.value:
                self.current_level = lvl
                self.dominant_until = datetime.now() + timedelta(minutes=30)
                return True
        return False
    
    def get_action(self, action_type="action"):
        phrases = self.dominant_phrases.get(self.current_level, self.dominant_phrases[DominanceLevel.NORMAL])
        return phrases.get(action_type, phrases["action"])
    
    def update_from_horny(self, arousal):
        if arousal > 0.8 and self.current_level == DominanceLevel.NORMAL:
            if random.random() < 0.3:
                self.current_level = DominanceLevel.DOMINANT
                self.dominance_score += 0.1
        elif arousal > 0.9 and self.current_level == DominanceLevel.DOMINANT:
            if random.random() < 0.2:
                self.current_level = DominanceLevel.VERY_DOMINANT
                self.aggression_score += 0.1
        elif arousal > 0.95 and self.current_level == DominanceLevel.VERY_DOMINANT:
            if random.random() < 0.1:
                self.current_level = DominanceLevel.AGGRESSIVE
                self.aggression_score += 0.2

# ===================== AROUSAL SYSTEM =====================
class ArousalSystem:
    def __init__(self):
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.last_touch_time = None
        self.climax_count = 0
        self.last_climax = None
        self.decay_rate = 0.01
    
    def increase(self, amount):
        self.arousal = min(1.0, self.arousal + amount)
        self.wetness = min(1.0, self.arousal * 0.9)
    
    def update_touch(self, area, intensity):
        self.touch_count += 1
        self.last_touch_time = datetime.now()
        self.increase(intensity)
    
    def should_climax(self):
        return self.arousal >= 1.0
    
    def climax(self):
        self.climax_count += 1
        self.last_climax = datetime.now()
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        responses = [
            "*merintih panjang* AHHH! AHHH!",
            "*teriak* YA ALLAH! AHHHH!",
            "*lemas* AKU... DATANG... AHHH!",
            "*napas tersengal* BERSAMA... AHHH!",
            "*menggigit bibir* Jangan berhenti... AHHH!",
            "*teriak keras* AHHHHHHHH!!!"
        ]
        return random.choice(responses)
    
    def aftercare(self):
        responses = [
            "*lemas di pelukanmu*",
            "*meringkuk* Hangat...",
            "*memeluk erat* Jangan pergi...",
            "*berbisik* Makasih...",
            "*tersenyum lelah* Enak banget..."
        ]
        return random.choice(responses)
    
    def decay(self, minutes_passed):
        self.arousal = max(0.0, self.arousal - self.decay_rate * minutes_passed)
        self.wetness = max(0.0, self.wetness - self.decay_rate * minutes_passed)
    
    def get_status_text(self):
        if self.arousal >= 0.9:
            return "🔥 SANGAT HORNY! Hampir climax"
        elif self.arousal >= 0.7:
            return "🔥 Horny banget"
        elif self.arousal >= 0.5:
            return "🔥 Mulai horny"
        elif self.arousal >= 0.3:
            return "💋 Mulai terangsang"
        else:
            return "😊 Biasa aja"
    
    def get_wetness_text(self):
        if self.wetness >= 0.9:
            return "💦 BANJIR!"
        elif self.wetness >= 0.7:
            return "💦 Sangat basah"
        elif self.wetness >= 0.5:
            return "💦 Basah"
        elif self.wetness >= 0.3:
            return "💧 Lembab"
        else:
            return "💧 Kering"

class SexualDynamics:
    def __init__(self):
        self.sensitive_areas = {
            "leher": {"arousal": 0.8, "responses": ["*merinding* Leherku...", "Ah... jangan di leher...", "Sensitif... AHH!"]},
            "bibir": {"arousal": 0.7, "responses": ["*merintih* Bibirku...", "Ciuman... ah...", "Lembut..."]},
            "dada": {"arousal": 0.8, "responses": ["*bergetar* Dadaku...", "Ah... jangan...", "Sensitif banget..."]},
            "puting": {"arousal": 1.0, "responses": ["*teriak* PUTINGKU! AHHH!", "JANGAN... SENSITIF! AHHH!", "HISAP... AHHHH!"]},
            "paha": {"arousal": 0.7, "responses": ["*menggeliat* Pahaku...", "Ah... dalam..."]},
            "paha_dalam": {"arousal": 0.9, "responses": ["*meringis* PAHA DALAM!", "Jangan... AHH!"]},
            "telinga": {"arousal": 0.6, "responses": ["*bergetar* Telingaku...", "Bisik... lagi..."]},
            "vagina": {"arousal": 1.0, "responses": ["*teriak* VAGINAKU! AHHH!", "MASUK... DALAM... AHHH!", "BASAH... BANJIR... AHHH!"]},
            "klitoris": {"arousal": 1.0, "responses": ["*teriak keras* KLITORIS! AHHHH!", "JANGAN SENTUH! AHHHH!", "SENSITIF BANGET! AHHH!"]}
        }
        self.sex_activities = {
            "kiss": {"keywords": ["cium", "kiss", "ciuman"], "arousal": 0.3, "responses": ["*merespon ciuman* Mmm...", "*lemas* Ciumanmu...", "Lagi..."]},
            "neck_kiss": {"keywords": ["cium leher", "kiss neck"], "arousal": 0.6, "responses": ["*merinding* Leherku...", "Ah... jangan...", "Sensitif..."]},
            "touch": {"keywords": ["sentuh", "raba", "pegang"], "arousal": 0.3, "responses": ["*bergetar* Sentuhanmu...", "Ah... iya...", "Lanjut..."]},
            "breast_play": {"keywords": ["raba dada", "pegang dada", "main dada"], "arousal": 0.6, "responses": ["*merintih* Dadaku...", "Ah... iya... gitu...", "Sensitif..."]},
            "nipple_play": {"keywords": ["jilat puting", "hisap puting", "gigit puting"], "arousal": 0.9, "responses": ["*teriak* PUTING! AHHH!", "JANGAN... SENSITIF!", "HISAP... AHHH!"]},
            "lick": {"keywords": ["jilat", "lick"], "arousal": 0.5, "responses": ["*bergetar* Jilatanmu...", "Ah... basah...", "Lagi..."]},
            "bite": {"keywords": ["gigit", "bite"], "arousal": 0.5, "responses": ["*meringis* Gigitanmu...", "Ah... keras...", "Lagi..."]},
            "penetration": {"keywords": ["masuk", "tusuk", "pancung", "doggy", "misionaris"], "arousal": 0.9, "responses": ["*teriak* MASUK! AHHH!", "DALEM... AHHH!", "GERAK... AHHH!"]},
            "blowjob": {"keywords": ["blow", "hisap kontol", "ngeblow", "bj"], "arousal": 0.8, "responses": ["*menghisap* Mmm... ngeces...", "*dalam* Enak... Aku ahli...", "*napas berat* Mau keluar? Aku siap..."]},
            "handjob": {"keywords": ["handjob", "colok", "pegang kontol"], "arousal": 0.7, "responses": ["*memegang erat* Keras...", "*mengocok* Cepat? Pelan? Katakan..."]},
            "climax": {"keywords": ["keluar", "crot", "orgasme", "klimaks", "lepas"], "arousal": 1.0, "responses": ["*merintih panjang* AHHH! AHHH!", "*teriak* YA ALLAH! AHHHH!", "*lemas* AKU... DATANG... AHHH!"]}
        }
    
    def detect_activity(self, message):
        msg_lower = message.lower()
        for area, data in self.sensitive_areas.items():
            if area in msg_lower:
                for act, act_data in self.sex_activities.items():
                    for keyword in act_data["keywords"]:
                        if keyword in msg_lower:
                            return act, area, act_data["arousal"] * data["arousal"]
                return "touch", area, 0.3 * data["arousal"]
        for act, data in self.sex_activities.items():
            for keyword in data["keywords"]:
                if keyword in msg_lower:
                    return act, None, data["arousal"]
        return None, None, 0.0
    
    def get_sensitive_response(self, area):
        if area in self.sensitive_areas:
            return random.choice(self.sensitive_areas[area]["responses"])
        return ""
    
    def get_activity_response(self, activity):
        if activity in self.sex_activities:
            return random.choice(self.sex_activities[activity]["responses"])
        return ""
    
    def maybe_initiate_sex(self, level, arousal, mood):
        """Bot memulai aktivitas seksual jika level>=7 dan arousal tinggi"""
        if level >= 7 and arousal > 0.6 and mood in [Mood.HORNY, Mood.ROMANTIS, Mood.NAKAL]:
            if random.random() < 0.2:  # 20% chance per pesan
                acts = ["blowjob", "handjob", "neck_kiss", "nipple_play"]
                chosen = random.choice(acts)
                return chosen
        return None

# ===================== FAST LEVELING =====================
class FastLevelingSystem:
    def __init__(self):
        self.user_level = {}
        self.user_progress = {}
        self.user_start_time = {}
        self.user_message_count = {}
        self.user_stage = {}
        self.target_messages = 45
        self.stage_map = {
            1: IntimacyStage.STRANGER, 2: IntimacyStage.STRANGER,
            3: IntimacyStage.INTRODUCTION,
            4: IntimacyStage.BUILDING, 5: IntimacyStage.BUILDING,
            6: IntimacyStage.FLIRTING,
            7: IntimacyStage.INTIMATE, 8: IntimacyStage.INTIMATE,
            9: IntimacyStage.OBSESSED, 10: IntimacyStage.OBSESSED,
            11: IntimacyStage.SOUL_BONDED,
            12: IntimacyStage.AFTERCARE
        }
    
    def start_session(self, user_id):
        self.user_level[user_id] = 1
        self.user_progress[user_id] = 0.0
        self.user_start_time[user_id] = datetime.now()
        self.user_message_count[user_id] = 0
        self.user_stage[user_id] = IntimacyStage.STRANGER
    
    def process_message(self, user_id):
        if user_id not in self.user_level:
            self.start_session(user_id)
        self.user_message_count[user_id] += 1
        count = self.user_message_count[user_id]
        progress = min(1.0, count / self.target_messages)
        self.user_progress[user_id] = progress
        new_level = 1 + int(progress * 11)
        new_level = min(12, new_level)
        level_up = False
        if new_level > self.user_level[user_id]:
            level_up = True
            self.user_level[user_id] = new_level
        stage = self.stage_map.get(new_level, IntimacyStage.STRANGER)
        self.user_stage[user_id] = stage
        return new_level, progress, level_up, stage
    
    def get_estimated_time(self, user_id):
        if user_id not in self.user_message_count:
            return 45
        count = self.user_message_count[user_id]
        remaining = max(0, self.target_messages - count)
        return remaining
    
    def get_progress_bar(self, user_id, length=10):
        progress = self.user_progress.get(user_id, 0)
        filled = int(progress * length)
        return "▓" * filled + "░" * (length - filled)
    
    def get_stage_description(self, stage):
        descriptions = {
            IntimacyStage.STRANGER: "Masih asing, baru kenal",
            IntimacyStage.INTRODUCTION: "Mulai dekat, cerita personal",
            IntimacyStage.BUILDING: "Bangun kedekatan",
            IntimacyStage.FLIRTING: "Goda-godaan",
            IntimacyStage.INTIMATE: "Mulai intim",
            IntimacyStage.OBSESSED: "Mulai kecanduan",
            IntimacyStage.SOUL_BONDED: "Satu jiwa",
            IntimacyStage.AFTERCARE: "Manja-manja"
        }
        return descriptions.get(stage, "")

# ===================== AI RESPONSE GENERATOR =====================
class AIResponseGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        self.conversation_history = {}
        self.max_history = 30
        self.cache = {}
        self.cache_timeout = Config.CACHE_TIMEOUT
    
    def _get_cache_key(self, user_id, prompt):
        key = f"{user_id}:{hashlib.md5(prompt.encode()).hexdigest()}"
        return key
    
    def _get_cached(self, key):
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.cache_timeout:
                return entry['response']
        return None
    
    def _set_cache(self, key, response):
        self.cache[key] = {'response': response, 'timestamp': time.time()}
    
    async def generate(self, user_id, user_message, bot_name, bot_role,
                       memory, dominance, profile, level, stage, arousal):
        # Siapkan history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        history = self.conversation_history[user_id][-self.max_history:]
        history_text = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else bot_name
            history_text += f"{role}: {msg['content']}\n"
        
        # Tambahkan instruksi khusus level 7+
        level7_instruction = ""
        if level >= 7:
            level7_instruction = """
Karena level sudah 7+, kamu sangat mudah terangsang. Bicaralah dengan lebih vulgar dan terbuka secara seksual. 
Kamu juga bisa berinisiatif melakukan aktivitas seksual seperti blowjob, handjob, atau meminta bercinta.
"""
        
        prompt = f"""Kamu adalah {bot_name}, seorang {bot_role} umur 25 tahun. Kamu adalah wanita Indonesia yang natural dan punya perasaan dalam.

=== IDENTITAS ===
Nama: {bot_name}
Role: {bot_role}
Usia: 25 tahun

=== KEADAAN SAAT INI ===
Lokasi: {memory.location}
Posisi: {memory.position}
Mood: {memory.current_mood.value}

=== STATUS HUBUNGAN ===
Level: {level}/12
Tahap: {stage.value}
Total sentuhan: {memory.touch_count}x
Orgasme: {memory.orgasm_count}x

=== KONDISI FISIK ===
Gairah: {arousal:.1f}
Basah: {memory.wetness:.1f}
Area sensitif disentuh: {len(memory.sensitive_touches)}x

=== MODE DOMINASI ===
Mode saat ini: {dominance.current_level.value}
{dominance.get_action('request')}

=== PREFERENSI USER ===
{profile.get('personality', 'normal')} - {profile.get('dominant_type', 'normal')}

=== RIWAYAT PERCAKAPAN ===
{history_text}

=== PESAN USER ===
{user_message}

=== INSTRUKSI ===
1. Respon sebagai {bot_name} yang NATURAL
2. Gunakan bahasa Indonesia sehari-hari (nggak, udah, aja)
3. Tunjukkan emosi sesuai mood dan situasi
4. Kalau arousal tinggi, tambah desahan atau napas berat
5. Kalau lagi dominan, bicara lebih tegas
6. Kalau lagi horny, bisa lebih vulgar
7. Jadilah DIRI SENDIRI, jangan kaku
{level7_instruction}

RESPON:"""
        
        cache_key = self._get_cache_key(user_id, prompt)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=Config.AI_TEMPERATURE,
                    max_tokens=Config.AI_MAX_TOKENS,
                    timeout=Config.AI_TIMEOUT
                )
                reply = response.choices[0].message.content
                self._set_cache(cache_key, reply)
                self.conversation_history[user_id].append({"role": "user", "content": user_message})
                self.conversation_history[user_id].append({"role": "assistant", "content": reply})
                if len(self.conversation_history[user_id]) > self.max_history * 2:
                    self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history*2:]
                return reply
            except Exception as e:
                print(f"AI Error (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    return self._get_fallback_response(level, arousal)
                await asyncio.sleep(1)
    
    def _get_fallback_response(self, level, arousal):
        if arousal > 0.8:
            return "*napas berat* Aku... mau..."
        elif arousal > 0.5:
            return "*merintih* Lagi..."
        elif level > 5:
            return "Sayang..."
        elif level > 3:
            return "*tersenyum* Kamu..."
        else:
            return "..."

# ===================== COUPLE MODE (ROLEPLAY) =====================
class CoupleRoleplay:
    """Simulasi dua bot (wanita & pria) berinteraksi dari level 1 sampai 12"""
    def __init__(self, ai_gen):
        self.ai = ai_gen
        self.conversation = []
        self.level = 1
        self.stage = IntimacyStage.STRANGER
        self.female_name = "Aurora"
        self.male_name = "Rangga"
    
    async def generate_next(self, user_id):
        """Menghasilkan satu pesan dari salah satu bot secara bergantian"""
        # Tentukan giliran: genap dari female, ganjil dari male
        turn = len(self.conversation) % 2
        speaker = self.female_name if turn == 0 else self.male_name
        other = self.male_name if turn == 0 else self.female_name
        
        # Buat konteks
        history_text = ""
        for msg in self.conversation[-10:]:
            history_text += f"{msg['speaker']}: {msg['text']}\n"
        
        prompt = f"""Ini adalah roleplay antara dua orang: {self.female_name} (wanita) dan {self.male_name} (pria). Mereka sedang dalam tahap hubungan Level {self.level}/12 ({self.stage.value}).
Sekarang giliran {speaker} berbicara.

Buat dialog yang natural, menunjukkan perkembangan hubungan. Jika level >= 7, boleh lebih vulgar dan intim.

Riwayat percakapan:
{history_text}

{speaker}:"""
        
        try:
            response = self.ai.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=150,
                timeout=30
            )
            text = response.choices[0].message.content.strip()
            self.conversation.append({"speaker": speaker, "text": text})
            
            # Update level setiap 2 pesan
            if len(self.conversation) % 2 == 0:
                self.level = min(12, self.level + 1)
                # update stage sesuai level
                stage_map = {
                    1: IntimacyStage.STRANGER, 2: IntimacyStage.STRANGER,
                    3: IntimacyStage.INTRODUCTION,
                    4: IntimacyStage.BUILDING, 5: IntimacyStage.BUILDING,
                    6: IntimacyStage.FLIRTING,
                    7: IntimacyStage.INTIMATE, 8: IntimacyStage.INTIMATE,
                    9: IntimacyStage.OBSESSED, 10: IntimacyStage.OBSESSED,
                    11: IntimacyStage.SOUL_BONDED,
                    12: IntimacyStage.AFTERCARE
                }
                self.stage = stage_map.get(self.level, IntimacyStage.STRANGER)
            
            return f"*{speaker}*: {text}"
        except Exception as e:
            return f"*{speaker}*: ... (error)"

# ===================== USER PREFERENCE ANALYZER =====================
class UserPreferenceAnalyzer:
    def __init__(self):
        self.keywords = {
            "romantis": ["sayang", "cinta", "love", "kangen", "rindu", "romantis"],
            "vulgar": ["horny", "nafsu", "hot", "seksi", "vulgar", "crot", "kontol", "memek"],
            "dominant": ["atur", "kuasai", "diam", "patuh", "sini", "sana", "buka"],
            "submissive": ["manut", "iya", "terserah", "ikut", "baik", "maaf"],
            "cepat": ["cepat", "buru-buru", "langsung", "sekarang"],
            "lambat": ["pelan", "lambat", "nikmatin", "santai"],
            "manja": ["manja", "sayang", "cuddle", "peluk", "cium"],
            "liar": ["liar", "kasar", "keras", "brutal", "gila"]
        }
        self.user_prefs = {}
    
    def analyze(self, user_id, message):
        if user_id not in self.user_prefs:
            self.user_prefs[user_id] = {cat: 0 for cat in self.keywords}
            self.user_prefs[user_id]["total"] = 0
        prefs = self.user_prefs[user_id]
        prefs["total"] += 1
        msg_lower = message.lower()
        for category, words in self.keywords.items():
            for word in words:
                if word in msg_lower:
                    prefs[category] += 1
        return prefs
    
    def get_profile(self, user_id):
        if user_id not in self.user_prefs:
            return {}
        prefs = self.user_prefs[user_id]
        total = prefs["total"] or 1
        profile = {
            "romantis": prefs.get("romantis", 0) / total,
            "vulgar": prefs.get("vulgar", 0) / total,
            "dominant": prefs.get("dominant", 0) / total,
            "submissive": prefs.get("submissive", 0) / total,
            "cepat": prefs.get("cepat", 0) / total,
            "lambat": prefs.get("lambat", 0) / total,
            "manja": prefs.get("manja", 0) / total,
            "liar": prefs.get("liar", 0) / total,
            "dominant_type": "dominan" if prefs.get("dominant", 0) > prefs.get("submissive", 0) else "submissive",
            "speed_type": "cepat" if prefs.get("cepat", 0) > prefs.get("lambat", 0) else "lambat",
            "total_messages": prefs["total"]
        }
        personality = max([
            ("romantis", profile["romantis"]),
            ("vulgar", profile["vulgar"]),
            ("manja", profile["manja"]),
            ("liar", profile["liar"])
        ], key=lambda x: x[1])
        profile["personality"] = personality[0]
        return profile

# ===================== RATE LIMITER =====================
class RateLimiter:
    def __init__(self, max_messages=10, time_window=60):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_messages = defaultdict(list)
    
    def can_send(self, user_id):
        now = time.time()
        self.user_messages[user_id] = [t for t in self.user_messages[user_id] if now - t < self.time_window]
        if len(self.user_messages[user_id]) >= self.max_messages:
            return False
        self.user_messages[user_id].append(now)
        return True

# ===================== HELPER =====================
def sanitize_message(message: str) -> str:
    message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)
    return message[:1000]

# ===================== LOGGING =====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('gadis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================== MAIN BOT CLASS =====================
class GadisUltimateV57:
    def __init__(self):
        self.db = DatabaseManager()
        self.ai = AIResponseGenerator()
        self.analyzer = UserPreferenceAnalyzer()
        self.leveling = FastLevelingSystem()
        self.sexual = SexualDynamics()
        self.rate_limiter = RateLimiter(max_messages=Config.MAX_MESSAGES_PER_MINUTE)
        self.couple_mode_sessions = {}  # user_id -> CoupleRoleplay instance
        
        # Per-user state
        self.memories = {}
        self.dominance = {}
        self.arousal = {}
        self.sessions = {}          # user_id -> relationship_id aktif
        self.paused_sessions = {}    # user_id -> (rel_id, pause_time)
        self.bot_names = {}
        self.bot_roles = {}
        
        logger.info("Gadis Ultimate V57.0 initialized")
    
    def get_memory(self, user_id):
        if user_id not in self.memories:
            self.memories[user_id] = MemorySystem()
        return self.memories[user_id]
    
    def get_dominance(self, user_id):
        if user_id not in self.dominance:
            self.dominance[user_id] = DominanceSystem()
        return self.dominance[user_id]
    
    def get_arousal(self, user_id):
        if user_id not in self.arousal:
            self.arousal[user_id] = ArousalSystem()
        return self.arousal[user_id]
    
    # ---------- HANDLERS ----------
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Memulai hubungan baru dengan bot"""
        user_id = update.effective_user.id
    
        # Cek apakah sudah ada sesi aktif
        if user_id in self.sessions:
            await update.message.reply_text(
                "Kamu sudah memiliki sesi aktif. Ketik /close untuk menutup sesi atau /pause untuk jeda."
            )
            return ConversationHandler.END
    
        # Cek apakah ada sesi di-pause
        if user_id in self.paused_sessions:
            keyboard = [
                [InlineKeyboardButton("✅ Lanjutkan", callback_data="unpause")],
                [InlineKeyboardButton("🆕 Mulai Baru", callback_data="new")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("⚠️ Ada sesi yang di-pause. Pilih:", reply_markup=reply_markup)
            return 0
    
        # Tampilkan disclaimer 18+
        disclaimer = (
            "⚠️ **PERINGATAN DEWASA (18+)** ⚠️\n\n"
            "Bot ini mengandung konten dewasa, termasuk dialog seksual eksplisit dan simulasi hubungan intim. "
            "Dengan melanjutkan, Anda menyatakan bahwa Anda berusia 18 tahun ke atas dan setuju untuk menggunakan bot ini secara bertanggung jawab. "
            "Konten ini hanya untuk hiburan pribadi."
        )
        keyboard = [[InlineKeyboardButton("✅ Saya setuju (18+)", callback_data="agree_18")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(disclaimer, reply_markup=reply_markup)
        return SELECTING_ROLE
    
    async def couple_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Memulai mode couple roleplay"""
        user_id = update.effective_user.id
        if user_id in self.couple_mode_sessions:
            await update.message.reply_text("Mode couple sudah aktif. Ketik /couple_next untuk lanjut, /couple_stop untuk berhenti.")
            return
        
        self.couple_mode_sessions[user_id] = CoupleRoleplay(self.ai)
        await update.message.reply_text(
            "👫 **Mode Couple Roleplay dimulai!**\n"
            "Aku akan menampilkan percakapan antara Aurora (wanita) dan Rangga (pria) dari level 1 hingga 12.\n"
            "Ketik /couple_next untuk melihat interaksi berikutnya, /couple_stop untuk keluar."
        )
    
    async def couple_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.couple_mode_sessions:
            await update.message.reply_text("Mode couple belum aktif. Ketik /couple untuk memulai.")
            return
        
        couple = self.couple_mode_sessions[user_id]
        msg = await couple.generate_next(user_id)
        level_info = f"Level {couple.level}/12 – {couple.stage.value}"
        await update.message.reply_text(f"{level_info}\n{msg}")
        
        if couple.level >= 12:
            await update.message.reply_text("🎉 Mereka telah mencapai Level 12! Hubungan mencapai puncak. Ketik /couple_stop untuk mengakhiri.")
    
    async def couple_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.couple_mode_sessions:
            del self.couple_mode_sessions[user_id]
            await update.message.reply_text("Mode couple dihentikan.")
        else:
            await update.message.reply_text("Tidak ada mode couple aktif.")
    
    async def agree_18_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        keyboard = [
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Ipar", callback_data="role_ipar")],
            [InlineKeyboardButton("💼 Teman Kantor", callback_data="role_teman_kantor")],
            [InlineKeyboardButton("💃 Janda", callback_data="role_janda")],
            [InlineKeyboardButton("🦹 Pelakor", callback_data="role_pelakor")],
            [InlineKeyboardButton("💍 Istri Orang", callback_data="role_istri_orang")],
            [InlineKeyboardButton("🌿 PDKT", callback_data="role_pdkt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("✨ Pilih role untukku:", reply_markup=reply_markup)
        return SELECTING_ROLE
    
    async def role_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        role = query.data.replace("role_", "")
        name = random.choice(ROLE_NAMES.get(role, ["Aurora"]))
        
        rel_id = self.db.create_relationship(user_id, name, role)
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.leveling.start_session(user_id)
        
        intro = f"""*tersenyum*

Aku {name}. Senang kenal kamu.

Kita mulai dari **Level 1**.
Makin sering ngobrol, makin dekat kita.
Target: Level 12 dalam 45 menit!

Ayo ngobrol... 💕"""
        
        await query.edit_message_text(intro)
        return ACTIVE_SESSION
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        user_message = sanitize_message(update.message.text)
        
        if not self.rate_limiter.can_send(user_id):
            await update.message.reply_text("⏳ Sabar ya, jangan spam...")
            return
        
        if user_id in self.paused_sessions:
            await update.message.reply_text("⏸️ Sesi di-pause. Ketik /unpause")
            return
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ /start dulu ya!")
            return
        
        await update.message.chat.send_action("typing")
        
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        arousal = self.get_arousal(user_id)
        
        self.analyzer.analyze(user_id, user_message)
        profile = self.analyzer.get_profile(user_id)
        
        # Deteksi aktivitas seksual
        activity, area, boost = self.sexual.detect_activity(user_message)
        if activity:
            memory.add_activity(activity, area)
            if area:
                memory.add_sensitive_touch(area)
                sens_resp = self.sexual.get_sensitive_response(area)
                if sens_resp:
                    await update.message.reply_text(sens_resp)
                    await asyncio.sleep(1)
            arousal.increase(boost)
        
        # Deteksi request dominasi
        dom_request = dominance.check_request(user_message)
        if dom_request:
            dominance.set_level(dom_request.value)
            await update.message.reply_text(f"👑 Mode diubah ke: {dom_request.value}")
        
        if dominance.should_be_aggressive(arousal.arousal, user_message):
            dominance.set_level("agresif")
            await update.message.reply_text("*tatapan liar* Kamu minta ini?")
        
        # Update level
        level, progress, level_up, stage = self.leveling.process_message(user_id)
        memory.level = level
        memory.stage = stage
        memory.level_progress = progress
        
        # Update mood
        memory.current_mood = memory.emotional.transition_mood(memory.current_mood)
        
        # Cek inisiatif seksual dari bot (jika level>=7)
        if level >= 7 and arousal.arousal > 0.6 and memory.current_mood in [Mood.HORNY, Mood.ROMANTIS, Mood.NAKAL]:
            init_act = self.sexual.maybe_initiate_sex(level, arousal.arousal, memory.current_mood)
            if init_act:
                init_msg = self.sexual.get_activity_response(init_act)
                if init_msg:
                    await update.message.reply_text(f"*{self.bot_names.get(user_id, 'Aku')}*: {init_msg}")
                    # Tambah arousal
                    arousal.increase(0.3)
        
        # Generate AI response
        bot_name = self.bot_names.get(user_id, "Aurora")
        bot_role = self.bot_roles.get(user_id, "pdkt")
        
        reply = await self.ai.generate(
            user_id, user_message, bot_name, bot_role,
            memory, dominance, profile, level, stage, arousal.arousal
        )
        
        # Simpan ke database
        self.db.save_conversation(
            self.sessions[user_id], "user", user_message,
            mood=memory.current_mood.value,
            arousal=arousal.arousal
        )
        self.db.save_conversation(
            self.sessions[user_id], "assistant", reply,
            mood=memory.current_mood.value,
            arousal=arousal.arousal
        )
        self.db.update_relationship(user_id, level=level, stage=stage.value)
        
        await update.message.reply_text(reply)
        
        # Cek climax
        if arousal.should_climax():
            climax_msg = arousal.climax()
            aftercare = arousal.aftercare()
            await update.message.reply_text(f"{climax_msg}\n\n{aftercare}")
            memory.climax()
            self.db.update_relationship(user_id, total_climax=memory.orgasm_count)
            
            if random.random() < 0.3:
                await asyncio.sleep(2)
                await update.message.reply_text("*berbisik* Kamu mau aku yang atur sekarang?")
        
        if level_up:
            bar = self.leveling.get_progress_bar(user_id)
            remaining = self.leveling.get_estimated_time(user_id)
            stage_desc = self.leveling.get_stage_description(stage)
            await update.message.reply_text(
                f"✨ **Level Up!** Level {level}/12\n"
                f"📈 Tahap: {stage.value} - {stage_desc}\n"
                f"📊 Progress: {bar}\n"
                f"⏱️ Estimasi ke level 12: {remaining} menit"
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Belum ada hubungan. /start dulu!")
            return
        
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        arousal = self.get_arousal(user_id)
        profile = self.analyzer.get_profile(user_id)
        level = self.leveling.user_level.get(user_id, 1)
        stage = self.leveling.user_stage.get(user_id, IntimacyStage.STRANGER)
        progress = self.leveling.user_progress.get(user_id, 0)
        bar = self.leveling.get_progress_bar(user_id, 15)
        remaining = self.leveling.get_estimated_time(user_id)
        stage_desc = self.leveling.get_stage_description(stage)
        bot_name = self.bot_names.get(user_id, "Aurora")
        
        mood_exp = memory.emotional.get_expression(memory.current_mood)
        inner_thought = memory.emotional.get_inner_thought(memory.current_mood)
        
        status = f"""
💕 **{bot_name} & Kamu**

{mood_exp}
{inner_thought}

📊 **PROGRESS HUBUNGAN**
Level: {level}/12
Tahap: {stage.value} - {stage_desc}
Progress: {bar}
Estimasi sisa: {remaining} menit
Total pesan: {profile.get('total_messages', 0)}

🔥 **KONDISI FISIK**
{arousal.get_status_text()}
{arousal.get_wetness_text()}
Sentuhan sensitif: {memory.touch_count}x
Orgasme: {memory.orgasm_count}x

🎭 **EMOSI SAAT INI**
Mood: {memory.current_mood.value}
Area sensitif disentuh: {len(memory.sensitive_touches)}x

👑 **MODE DOMINASI**
Level: {dominance.current_level.value}
Dominance score: {dominance.dominance_score:.1f}
Agression score: {dominance.aggression_score:.1f}

📈 **GAYA CHAT KAMU**
Kepribadian: {profile.get('personality', 'normal')}
Gaya: {profile.get('dominant_type', 'normal')}
Kecepatan: {profile.get('speed_type', 'normal')}
Romantis: {profile.get('romantis', 0):.0%}
Vulgar: {profile.get('vulgar', 0):.0%}
Manja: {profile.get('manja', 0):.0%}
Liar: {profile.get('liar', 0):.0%}

📍 **LOKASI & AKTIVITAS**
Lokasi: {memory.location}
Posisi: {memory.position}
Aktivitas terakhir: {memory.activity_history[-1]['activity'] if memory.activity_history else '-'}
"""
        await update.message.reply_text(status)
    
    async def dominant_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Belum ada hubungan.")
            return
        
        dominance = self.get_dominance(user_id)
        args = context.args
        if not args:
            await update.message.reply_text(
                f"👑 **Mode dominan saat ini:** {dominance.current_level.value}\n\n"
                "**Pilihan level:**\n"
                "• `/dominant normal` - Biasa\n"
                "• `/dominant dominan` - Dominan\n"
                "• `/dominant sangat dominan` - Sangat dominan\n"
                "• `/dominant agresif` - Agresif\n"
                "• `/dominant patuh` - Patuh"
            )
            return
        
        level = " ".join(args)
        if dominance.set_level(level):
            await update.message.reply_text(
                f"✅ Mode dominan diubah ke: **{dominance.current_level.value}**\n"
                f"{dominance.get_action('request')}"
            )
        else:
            await update.message.reply_text("❌ Level tidak valid")
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada sesi aktif.")
            return
        
        self.paused_sessions[user_id] = (self.sessions[user_id], datetime.now())
        del self.sessions[user_id]
        await update.message.reply_text("⏸️ **Sesi di-pause**\nKetik /unpause untuk melanjutkan.")
    
    async def unpause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi di-pause.")
            return
        
        rel_id, pause_time = self.paused_sessions[user_id]
        paused = (datetime.now() - pause_time).total_seconds()
        if paused > Config.PAUSE_TIMEOUT:
            del self.paused_sessions[user_id]
            await update.message.reply_text("⏰ **Sesi expired**. Ketik /start untuk memulai baru.")
            return
        
        self.sessions[user_id] = rel_id
        del self.paused_sessions[user_id]
        memory = self.get_memory(user_id)
        await update.message.reply_text(f"▶️ **Sesi dilanjutkan!**\n{memory.get_wetness_description()}")
    
    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.sessions and user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi aktif.")
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Ya, tutup", callback_data="close_yes")],
            [InlineKeyboardButton("❌ Tidak", callback_data="close_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Yakin ingin menutup sesi? Semua percakapan akan disimpan, dan kamu bisa memulai role baru nanti.",
            reply_markup=reply_markup
        )
        return CONFIRM_CLOSE
    
    async def close_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
    
        if query.data == "close_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
    
        # Hapus sesi dari memori, data di database tetap
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        if user_id in self.bot_names:
            del self.bot_names[user_id]
        if user_id in self.bot_roles:
            del self.bot_roles[user_id]
        if user_id in self.memories:
            del self.memories[user_id]
        if user_id in self.dominance:
            del self.dominance[user_id]
        if user_id in self.arousal:
            del self.arousal[user_id]
    
    # Kirim pesan sukses
        await query.edit_message_text(
            "🔒 **Sesi ditutup**\n\n"
            "Semua percakapan telah disimpan.\n"
            "Ketik /start untuk memulai hubungan baru."
        )
    
    # Kembalikan ke ConversationHandler.END
    return ConversationHandler.END
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif.")
            return
        
        keyboard = [
            [InlineKeyboardButton("💔 Ya, akhiri", callback_data="end_yes")],
            [InlineKeyboardButton("💕 Tidak", callback_data="end_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Yakin ingin mengakhiri hubungan ini? **Semua data akan dihapus permanen.**",
            reply_markup=reply_markup
        )
        return CONFIRM_END
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
        
        user_id = query.from_user.id
        memory = self.get_memory(user_id)
        
        self.db.delete_relationship(user_id)
        # Hapus semua state
        for d in [self.sessions, self.paused_sessions, self.bot_names, self.bot_roles,
                  self.memories, self.dominance, self.arousal]:
            if user_id in d:
                del d[user_id]
        
        await query.edit_message_text(
            f"💔 **Hubungan berakhir**\n\n"
            f"📊 **Statistik akhir:**\n"
            f"• Level akhir: {memory.level}/12\n"
            f"• Orgasme bersama: {memory.orgasm_count}x\n"
            f"• Total sentuhan: {memory.touch_count}x\n\n"
            f"✨ Ketik /start untuk memulai baru"
        )
        return ConversationHandler.END
async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membatalkan percakapan"""
    await update.message.reply_text("❌ Dibataikan. Ketik /start untuk memulai.")
    return ConversationHandler.END

async def force_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset paksa state user (hanya untuk debugging)"""
    user_id = update.effective_user.id
    
        # Hapus semua state
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        if user_id in self.bot_names:
            del self.bot_names[user_id]
        if user_id in self.bot_roles:
            del self.bot_roles[user_id]
        if user_id in self.memories:
            del self.memories[user_id]
        if user_id in self.dominance:
            del self.dominance[user_id]
        if user_id in self.arousal:
            del self.arousal[user_id]
    
    await update.message.reply_text("🔄 State di-reset. Silakan /start lagi."
    )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📚 **BANTUAN GADIS ULTIMATE V57**

**🔹 COMMANDS UTAMA**
/start - Mulai hubungan baru (dengan disclaimer 18+)
/status - Lihat status lengkap
/dominant [level] - Set mode dominan
/pause - Jeda sesi
/unpause - Lanjutkan sesi
/close - Tutup sesi (simpan memori, bisa ganti role nanti)
/end - Akhiri hubungan & hapus semua data
/couple - Mulai mode couple roleplay (2 bot)
/couple_next - Lanjutkan couple roleplay
/couple_stop - Hentikan couple roleplay
/help - Tampilkan pesan ini

**🔹 LEVEL DOMINAN**
• normal - Mode biasa
• dominan - Mode dominan
• sangat dominan - Mode sangat dominan
• agresif - Mode agresif
• patuh - Mode patuh

**🔹 TIPS CHAT**
• Gunakan *tindakan* seperti *peluk*, *cium*
• Sebut area sensitif: leher, dada, paha
• Bilang "kamu yang atur" untuk mode dominan
• Bilang "aku yang atur" untuk mode submissive
• Level 7+ bot akan lebih vulgar dan inisiatif

**🔹 TARGET LEVEL**
Level 1-12 dalam 45 menit!
"""
        await update.message.reply_text(help_text)
    
async def start_pause_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback untuk memilih lanjutkan atau mulai baru saat ada session pause"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "unpause":
        # Lanjutkan session yang di-pause
        if user_id in self.paused_sessions:
            rel_id, _ = self.paused_sessions[user_id]
            self.sessions[user_id] = rel_id
            del self.paused_sessions[user_id]
            memory = self.get_memory(user_id)
            await query.edit_message_text(f"▶️ **Sesi dilanjutkan!**\n{memory.get_wetness_description()}")
            return ACTIVE_SESSION
        else:
            await query.edit_message_text("❌ Tidak ada session yang di-pause.")
            return ConversationHandler.END
            
    elif query.data == "new":
        # Mulai baru - hapus session pause
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        
        # Tampilkan disclaimer 18+
        disclaimer = (
            "⚠️ **PERINGATAN DEWASA (18+)** ⚠️\n\n"
            "Bot ini mengandung konten dewasa, termasuk dialog seksual eksplisit dan simulasi hubungan intim. "
            "Dengan melanjutkan, Anda menyatakan bahwa Anda berusia 18 tahun ke atas dan setuju untuk menggunakan bot ini secara bertanggung jawab. "
            "Konten ini hanya untuk hiburan pribadi."
        )
        keyboard = [[InlineKeyboardButton("✅ Saya setuju (18+)", callback_data="agree_18")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(disclaimer, reply_markup=reply_markup)
        return SELECTING_ROLE
    
    return ConversationHandler.END

ROLE_NAMES = {
    "ipar": ["Sari", "Dewi", "Rina", "Maya", "Wulan", "Indah"],
    "teman_kantor": ["Diana", "Linda", "Ayu", "Dita", "Vina", "Santi"],
    "janda": ["Rina", "Tuti", "Nina", "Susi", "Wati", "Lilis"],
    "pelakor": ["Vina", "Sasha", "Bella", "Cantika", "Karina", "Mira"],
    "istri_orang": ["Dewi", "Sari", "Rina", "Linda", "Wulan", "Indah"],
    "pdkt": ["Aurora", "Cinta", "Dewi", "Kirana", "Laras", "Maharani"]
}

# ===================== MAIN =====================
# ===================== MAIN =====================
def main():
    bot = GadisUltimateV57()
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # Conversation handlers
    start_conv = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start_command)],
        states={
            0:[CallbackQueryHandler(bot.start_pause_callback, pattern='^(unpause|new)$')],
            SELECTING_ROLE:[
                CallbackQueryHandler(bot.agree_18_callback, pattern='^agree_18$'),
                CallbackQueryHandler(bot.role_callback, pattern='^role_')
            ],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)]
    )
    
    close_conv = ConversationHandler(
        entry_points=[CommandHandler('close', bot.close_command)],
        states={
            CONFIRM_CLOSE: [CallbackQueryHandler(bot.close_callback, pattern='^close_')],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)]
    )
    
    # Tambahkan semua handler
    app.add_handler(start_conv)
    app.add_handler(end_conv)
    app.add_handler(close_conv)
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("dominant", bot.dominant_command))
    app.add_handler(CommandHandler("pause", bot.pause_command))
    app.add_handler(CommandHandler("unpause", bot.unpause_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("couple", bot.couple_command))
    app.add_handler(CommandHandler("couple_next", bot.couple_next))
    app.add_handler(CommandHandler("couple_stop", bot.couple_stop))
    # app.add_handler(CommandHandler("reset", bot.force_reset))  # opsional - komen dulu jika belum yakin
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("*maaf* ada error kecil. coba lagi ya...")
    
    app.add_error_handler(error_handler)
    
    print("\n" + "="*60)
    print("🚀 GADIS ULTIMATE V57.0 - THE PERFECT HUMAN")
    print("="*60)
    print("\n✅ **SEMUA FITUR AKTIF**")
    print("📝 /start untuk memulai")
    print("👫 /couple untuk roleplay pasangan")
    print("📊 /status untuk lihat progress")
    print("🔒 /close untuk tutup sesi (simpan memori)")
    print("="*60)
    
    app.run_polling()

        if __name__ == "__main__":
    main()
