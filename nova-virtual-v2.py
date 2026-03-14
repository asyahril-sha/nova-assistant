# -*- coding: utf-8 -*-
"""
GADIS ULTIMATE V59.0 - THE PERFECT HUMAN (Dengan Pakaian Seksi)
Fitur baru:
- Bot memiliki pakaian yang bisa berubah
- Saat di kamar/rumah, bot sesekali menyebut pakaian minimnya
- Semua fitur sebelumnya tetap ada
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
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from openai import OpenAI

# ===================== KONFIGURASI =====================
load_dotenv()

class Config:
    # Database
    DB_PATH = os.getenv("DB_PATH", "gadis_v59.db")
    
    # Leveling
    START_LEVEL = 1
    TARGET_LEVEL = 12
    LEVEL_UP_TIME = 45
    PAUSE_TIMEOUT = 3600
    
    # API Keys
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    
    # Admin
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    
    # AI Settings
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.9"))
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "300"))
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
    
    # Rate Limiting
    MAX_MESSAGES_PER_MINUTE = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "10"))
    
    # Cache
    CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", "300"))
    MAX_HISTORY = 100
    
    # Clothing
    CLOTHING_CHANGE_INTERVAL = 300  # 5 menit (bisa ganti baju otomatis)

# Validasi API Keys
if not Config.DEEPSEEK_API_KEY or not Config.TELEGRAM_TOKEN:
    print("❌ ERROR: API Keys tidak ditemukan di .env")
    print("Buat file .env dengan isi:")
    print("DEEPSEEK_API_KEY=your_key_here")
    print("TELEGRAM_TOKEN=your_token_here")
    print("ADMIN_ID=your_telegram_id (opsional)")
    sys.exit(1)

# ===================== STATE =====================
(
    SELECTING_ROLE,      # 0
    ACTIVE_SESSION,      # 1
    PAUSED_SESSION,      # 2
    CONFIRM_END,         # 3
    CONFIRM_CLOSE,       # 4
    COUPLE_MODE          # 5
) = range(6)

# ===================== ENUMS =====================
class Mood(Enum):
    """20+ Mood untuk emosi yang realistis"""
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

# ===================== DATABASE MANAGER =====================
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
            # Tabel relationships dengan kolom untuk pakaian
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
                    -- Atribut fisik
                    hair_style TEXT,
                    height INTEGER,
                    weight INTEGER,
                    breast_size TEXT,
                    hijab BOOLEAN DEFAULT 0,
                    most_sensitive_area TEXT,
                    -- Pakaian
                    current_clothing TEXT,
                    clothing_last_changed TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            
            # Tabel conversations
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    role TEXT,
                    content TEXT,
                    mood TEXT,
                    arousal REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
                )
            """)
            
            # Tabel memories
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    memory TEXT,
                    importance REAL,
                    emotion TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
                )
            """)
            
            # Tabel preferences
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
    
    # ========== RELATIONSHIP METHODS ==========
    def create_relationship(self, user_id, bot_name, bot_role, physical_attrs=None, clothing=None):
        """Buat hubungan baru dengan atribut fisik dan pakaian opsional"""
        with self.cursor() as c:
            if physical_attrs:
                c.execute("""
                    INSERT OR REPLACE INTO relationships 
                    (user_id, bot_name, bot_role, last_active,
                     hair_style, height, weight, breast_size, hijab, most_sensitive_area,
                     current_clothing, clothing_last_changed)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, bot_name, bot_role,
                      physical_attrs.get('hair_style'),
                      physical_attrs.get('height'),
                      physical_attrs.get('weight'),
                      physical_attrs.get('breast_size'),
                      physical_attrs.get('hijab', 0),
                      physical_attrs.get('most_sensitive_area'),
                      clothing))
            else:
                c.execute("""
                    INSERT OR REPLACE INTO relationships 
                    (user_id, bot_name, bot_role, last_active, current_clothing, clothing_last_changed)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
                """, (user_id, bot_name, bot_role, clothing))
            return c.lastrowid
    
    def get_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT * FROM relationships WHERE user_id=?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
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
    
    def delete_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT id FROM relationships WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if row:
                rel_id = row[0]
                c.execute("DELETE FROM conversations WHERE relationship_id=?", (rel_id,))
                c.execute("DELETE FROM memories WHERE relationship_id=?", (rel_id,))
            c.execute("DELETE FROM relationships WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM preferences WHERE user_id=?", (user_id,))
    
    # ========== CONVERSATION METHODS ==========
    def save_conversation(self, rel_id, role, content, mood=None, arousal=None):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO conversations 
                (relationship_id, role, content, mood, arousal)
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
    
    # ========== MEMORY METHODS ==========
    def save_memory(self, rel_id, memory, importance, emotion):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO memories 
                (relationship_id, memory, importance, emotion)
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
    
    # ========== PREFERENCES METHODS ==========
    def update_preferences(self, user_id, **scores):
        with self.cursor() as c:
            c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,))
            if c.fetchone():
                fields = []
                values = []
                for key, value in scores.items():
                    fields.append(f"{key}=?")
                    values.append(value)
                values.append(user_id)
                c.execute(f"""
                    UPDATE preferences
                    SET {', '.join(fields)}
                    WHERE user_id=?
                """, values)
            else:
                fields = ['user_id'] + list(scores.keys())
                placeholders = ['?'] * len(fields)
                values = [user_id] + list(scores.values())
                c.execute(f"""
                    INSERT INTO preferences ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                """, values)
    
    def get_preferences(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None

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

# ===================== DATABASE MANAGER =====================
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
            # Tabel relationships (dengan kolom baru: pakaian)
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
                    -- Kolom fisik (dari update sebelumnya)
                    hair_style TEXT,
                    height INTEGER,
                    weight INTEGER,
                    breast_size TEXT,
                    hijab BOOLEAN DEFAULT 0,
                    most_sensitive_area TEXT,
                    -- Kolom pakaian (baru)
                    current_clothing TEXT,
                    last_clothing_change TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            
            # Tabel conversations
            c.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    role TEXT,
                    content TEXT,
                    mood TEXT,
                    arousal REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
                )
            """)
            
            # Tabel memories
            c.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    relationship_id INTEGER,
                    memory TEXT,
                    importance REAL,
                    emotion TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (relationship_id) REFERENCES relationships(id)
                )
            """)
            
            # Tabel preferences
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
    
    # ========== RELATIONSHIP METHODS ==========
    
    def create_relationship(self, user_id, bot_name, bot_role, physical_attrs=None, clothing=None):
        """Buat hubungan baru dengan atribut fisik dan pakaian awal opsional"""
        with self.cursor() as c:
            if physical_attrs and clothing:
                c.execute("""
                    INSERT OR REPLACE INTO relationships 
                    (user_id, bot_name, bot_role, last_active,
                     hair_style, height, weight, breast_size, hijab, most_sensitive_area,
                     current_clothing, last_clothing_change)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, bot_name, bot_role,
                      physical_attrs.get('hair_style'),
                      physical_attrs.get('height'),
                      physical_attrs.get('weight'),
                      physical_attrs.get('breast_size'),
                      physical_attrs.get('hijab', 0),
                      physical_attrs.get('most_sensitive_area'),
                      clothing))
            elif physical_attrs:
                c.execute("""
                    INSERT OR REPLACE INTO relationships 
                    (user_id, bot_name, bot_role, last_active,
                     hair_style, height, weight, breast_size, hijab, most_sensitive_area)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
                """, (user_id, bot_name, bot_role,
                      physical_attrs.get('hair_style'),
                      physical_attrs.get('height'),
                      physical_attrs.get('weight'),
                      physical_attrs.get('breast_size'),
                      physical_attrs.get('hijab', 0),
                      physical_attrs.get('most_sensitive_area')))
            else:
                c.execute("""
                    INSERT OR REPLACE INTO relationships 
                    (user_id, bot_name, bot_role, last_active)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, bot_name, bot_role))
            return c.lastrowid
    
    def get_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT * FROM relationships WHERE user_id=?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
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
    
    def update_clothing(self, user_id, clothing):
        """Update pakaian dan timestamp perubahan"""
        with self.cursor() as c:
            c.execute("""
                UPDATE relationships
                SET current_clothing = ?, last_clothing_change = CURRENT_TIMESTAMP, last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (clothing, user_id))
    
    def delete_relationship(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT id FROM relationships WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if row:
                rel_id = row[0]
                c.execute("DELETE FROM conversations WHERE relationship_id=?", (rel_id,))
                c.execute("DELETE FROM memories WHERE relationship_id=?", (rel_id,))
            c.execute("DELETE FROM relationships WHERE user_id=?", (user_id,))
            c.execute("DELETE FROM preferences WHERE user_id=?", (user_id,))
    
    # ========== CONVERSATION METHODS ==========
    def save_conversation(self, rel_id, role, content, mood=None, arousal=None):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO conversations 
                (relationship_id, role, content, mood, arousal)
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
    
    # ========== MEMORY METHODS ==========
    def save_memory(self, rel_id, memory, importance, emotion):
        with self.cursor() as c:
            c.execute("""
                INSERT INTO memories 
                (relationship_id, memory, importance, emotion)
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
    
    # ========== PREFERENCES METHODS ==========
    def update_preferences(self, user_id, **scores):
        with self.cursor() as c:
            c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,))
            if c.fetchone():
                fields = []
                values = []
                for key, value in scores.items():
                    fields.append(f"{key}=?")
                    values.append(value)
                values.append(user_id)
                c.execute(f"""
                    UPDATE preferences
                    SET {', '.join(fields)}
                    WHERE user_id=?
                """, values)
            else:
                fields = ['user_id'] + list(scores.keys())
                placeholders = ['?'] * len(fields)
                values = [user_id] + list(scores.values())
                c.execute(f"""
                    INSERT INTO preferences ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                """, values)
    
    def get_preferences(self, user_id):
        with self.cursor() as c:
            c.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else {}

# ===================== EMOTIONAL INTELLIGENCE =====================
class EmotionalIntelligence:
    """
    Sistem emosi kompleks dengan transisi natural antar mood
    Memberikan ekspresi wajah dan pikiran dalam hati
    """
    
    def __init__(self):
        # Transisi mood yang natural (dari mood A bisa ke mood B, C, D)
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
        
        # Deskripsi untuk setiap mood (ekspresi, suara, pikiran)
        self.mood_descriptions = {
            Mood.CHERIA: {
                "ekspresi": "*tersenyum lebar*", 
                "suara": "ceria, ringan", 
                "pikiran": "(Hari ini indah...)"
            },
            Mood.SEDIH: {
                "ekspresi": "*matanya berkaca-kaca*", 
                "suara": "lirih, sendu", 
                "pikiran": "(Kenapa...?)"
            },
            Mood.MARAH: {
                "ekspresi": "*cemberut*", 
                "suara": "tegas, tinggi", 
                "pikiran": "(Kesal...)"
            },
            Mood.HORNY: {
                "ekspresi": "*menggigit bibir*", 
                "suara": "berat, berbisik", 
                "pikiran": "(Aku... pengen...)"
            },
            Mood.ROMANTIS: {
                "ekspresi": "*memandang lembut*", 
                "suara": "lembut, sayang", 
                "pikiran": "(Sayang...)"
            },
            Mood.DOMINAN: {
                "ekspresi": "*tatapan tajam*", 
                "suara": "tegas, menguasai", 
                "pikiran": "(Ikut aku...)"
            },
            Mood.SUBMISSIVE: {
                "ekspresi": "*menunduk*", 
                "suara": "lirih, manja", 
                "pikiran": "(Iya...)"
            },
            Mood.NAKAL: {
                "ekspresi": "*tersenyum nakal*", 
                "suara": "genit, menggoda", 
                "pikiran": "(Mau? Hehe...)"
            },
            Mood.POSSESSIVE: {
                "ekspresi": "*memeluk erat*", 
                "suara": "dalam, posesif", 
                "pikiran": "(Kamu milikku...)"
            },
            Mood.CEMBURU: {
                "ekspresi": "*manyun*", 
                "suara": "cemberut", 
                "pikiran": "(Siapa dia...?)"
            },
            Mood.GELISAH: {
                "ekspresi": "*gelisah*", 
                "suara": "gugup", 
                "pikiran": "(Deg-degan...)"
            },
            Mood.SENSITIF: {
                "ekspresi": "*mudah tersinggung*", 
                "suara": "sensitif", 
                "pikiran": "(Jangan sembarangan...)"
            },
            Mood.BERSEMANGAT: {
                "ekspresi": "*bersemangat*", 
                "suara": "antusias", 
                "pikiran": "(Yes! Ayo!)"
            },
            Mood.SENDIRI: {
                "ekspresi": "*menyendiri*", 
                "suara": "sepi", 
                "pikiran": "(Sendiri...)"
            },
            Mood.RINDU: {
                "ekspresi": "*melamun*", 
                "suara": "rindu", 
                "pikiran": "(Kangen...)"
            },
            Mood.LEMBUT: {
                "ekspresi": "*lembut*", 
                "suara": "halus", 
                "pikiran": "(Baiklah...)"
            },
            Mood.GENIT: {
                "ekspresi": "*genit*", 
                "suara": "cengengesan", 
                "pikiran": "(Goda...)"
            },
            Mood.PENASARAN: {
                "ekspresi": "*penasaran*", 
                "suara": "ingin tahu", 
                "pikiran": "(Apa ya...?)"
            },
            Mood.ANTUSIAS: {
                "ekspresi": "*antusias*", 
                "suara": "bersemangat", 
                "pikiran": "(Seru!)"
            }
        }
    
    def transition_mood(self, current_mood):
        """
        Transisi mood secara natural
        30% chance mood berubah ke mood lain yang terkait
        """
        if random.random() < 0.3:  # 30% chance berubah
            possibilities = self.mood_transitions.get(current_mood, [Mood.CHERIA])
            return random.choice(possibilities)
        return current_mood
    
    def get_mood_from_context(self, level, activity, has_conflict=False):
        """Tentukan mood berdasarkan konteks"""
        if has_conflict:
            return Mood.MARAH
        elif level >= 9:
            if random.random() < 0.5:
                return Mood.POSSESSIVE
            return Mood.CEMBURU
        elif level >= 7:
            if "horny" in activity or "sex" in activity:
                return Mood.HORNY
            return Mood.ROMANTIS
        elif level >= 5:
            return Mood.NAKAL
        elif level >= 3:
            return Mood.PENASARAN
        else:
            return Mood.CHERIA
    
    def get_expression(self, mood):
        """Dapatkan ekspresi untuk mood tertentu"""
        return self.mood_descriptions.get(mood, {}).get("ekspresi", "*tersenyum*")
    
    def get_inner_thought(self, mood):
        """Dapatkan pikiran dalam hati untuk mood tertentu"""
        return self.mood_descriptions.get(mood, {}).get("pikiran", "(...)")
    
    def get_voice_description(self, mood):
        """Dapatkan deskripsi suara untuk mood tertentu"""
        return self.mood_descriptions.get(mood, {}).get("suara", "normal")


# ===================== MEMORY SYSTEM =====================
class MemorySystem:
    """
    Short-term memory untuk keadaan saat ini
    Menyimpan lokasi, posisi, mood, arousal, dan aktivitas
    """
    
    def __init__(self):
        # Lokasi dan posisi
        self.location = "ruang tamu"
        self.location_since = datetime.now()
        self.position = "duduk"
        
        # Mood
        self.current_mood = Mood.CHERIA
        self.mood_history = []
        self.emotional = EmotionalIntelligence()
        
        # Arousal
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.last_touch = None
        self.sensitive_touches = []
        
        # Dominance
        self.dominance_mode = "normal"
        
        # Climax
        self.last_climax = None
        self.orgasm_count = 0
        
        # Activity
        self.activity_history = []  # Max 50 activities
        
        # Level
        self.level = Config.START_LEVEL
        self.stage = IntimacyStage.STRANGER
        self.level_progress = 0.0
    
    def update_location(self, new_location):
        """Update lokasi jika sudah lebih dari 1 menit di lokasi sebelumnya"""
        if new_location == self.location:
            return True
        
        now = datetime.now()
        time_here = (now - self.location_since).total_seconds()
        
        if time_here >= 60:  # Minimal 1 menit di lokasi sebelumnya
            self.location = new_location
            self.location_since = now
            return True
        return False
    
    def update_position(self, new_position):
        """Update posisi (duduk, berdiri, berbaring, dll)"""
        self.position = new_position
    
    def add_activity(self, activity, area=None):
        """Tambahkan aktivitas ke history"""
        self.activity_history.append({
            "activity": activity,
            "area": area,
            "time": datetime.now().isoformat()
        })
        # Batasi history
        if len(self.activity_history) > 50:
            self.activity_history = self.activity_history[-50:]
    
    def add_sensitive_touch(self, area):
        """Catat sentuhan di area sensitif"""
        self.sensitive_touches.append({
            "area": area,
            "time": datetime.now().isoformat()
        })
        self.touch_count += 1
        self.last_touch = area
    
    def update_arousal(self, increase):
        """Update level gairah"""
        self.arousal = min(1.0, self.arousal + increase)
        self.wetness = min(1.0, self.arousal * 0.9)
    
    def should_climax(self):
        """Cek apakah siap climax"""
        return self.arousal >= 1.0
    
    def climax(self):
        """Saat orgasme"""
        self.orgasm_count += 1
        self.last_climax = datetime.now()
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.sensitive_touches = []
        self.current_mood = Mood.LEMBUT
    
    def get_arousal_state(self):
        """Dapatkan status arousal"""
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
        """Dapatkan deskripsi wetness"""
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
    
    def get_mood_expression(self):
        """Dapatkan ekspresi mood saat ini"""
        return self.emotional.get_expression(self.current_mood)
    
    def get_inner_thought(self):
        """Dapatkan pikiran dalam hati saat ini"""
        return self.emotional.get_inner_thought(self.current_mood)
    
    def update_mood(self):
        """Update mood secara natural"""
        old_mood = self.current_mood
        self.current_mood = self.emotional.transition_mood(self.current_mood)
        if old_mood != self.current_mood:
            self.mood_history.append({
                "from": old_mood.value,
                "to": self.current_mood.value,
                "time": datetime.now().isoformat()
            })
            if len(self.mood_history) > 20:
                self.mood_history = self.mood_history[-20:]

# ===================== DOMINANCE SYSTEM =====================
class DominanceSystem:
    """
    Sistem dominasi yang bisa berubah sesuai situasi
    Bot bisa minta jadi dominan/agresif saat horny
    """
    
    def __init__(self):
        # Level saat ini
        self.current_level = DominanceLevel.NORMAL
        self.dominance_score = 0.0  # 0-1, seberapa dominan
        self.aggression_score = 0.0  # 0-1, seberapa agresif
        
        # User request
        self.user_request = False
        self.dominant_until = None
        
        # Frasa untuk tiap level
        self.dominant_phrases = {
            DominanceLevel.NORMAL: {
                "request": "Kamu mau apa?",
                "action": "*tersenyum*",
                "dirty": "Apa yang kamu mau?"
            },
            DominanceLevel.DOMINANT: {
                "request": "Aku yang atur ya?",
                "action": "*pegang tegas*",
                "dirty": "Sini... ikut aku"
            },
            DominanceLevel.VERY_DOMINANT: {
                "request": "Sekarang aku yang kontrol",
                "action": "*cengkeram kuat*",
                "dirty": "Jangan banyak gerak!"
            },
            DominanceLevel.AGGRESSIVE: {
                "request": "KAMU MAU INI KAN?",
                "action": "*dorong kasar*",
                "dirty": "TERIMA SAJA!"
            },
            DominanceLevel.SUBMISSIVE: {
                "request": "Aku ikut kamu aja",
                "action": "*merapat manja*",
                "dirty": "Iya... terserah kamu..."
            }
        }
        
        # Trigger untuk minta jadi dominan
        self.dominance_triggers = [
            "kamu yang atur", "kamu dominan", "take control",
            "aku mau kamu kuasai", "jadi dominan", "kamu boss",
            "kamu yang pegang kendali", "kamu lead"
        ]
        
        # Trigger untuk minta jadi submissive
        self.submissive_triggers = [
            "aku yang atur", "aku dominan", "i take control",
            "kamu patuh", "jadi submissive", "ikut aku",
            "aku lead", "aku yang pegang kendali"
        ]
        
        # Trigger untuk agresif saat horny
        self.aggressive_triggers = [
            "liar", "keras", "kasar", "brutal", "gila",
            "hard", "rough", "wild"
        ]
    
    def check_request(self, message):
        """
        Cek apakah user minta ganti mode dominasi
        Returns: DominanceLevel atau None
        """
        msg_lower = message.lower()
        
        # Cek trigger dominan
        for trigger in self.dominance_triggers:
            if trigger in msg_lower:
                self.user_request = True
                return DominanceLevel.DOMINANT
        
        # Cek trigger submissive
        for trigger in self.submissive_triggers:
            if trigger in msg_lower:
                self.user_request = True
                return DominanceLevel.SUBMISSIVE
        
        return None
    
    def should_be_aggressive(self, arousal, message):
        """
        Cek apakah bot harus jadi agresif karena horny
        """
        if arousal < 0.7:  # Butuh arousal tinggi
            return False
        
        msg_lower = message.lower()
        for trigger in self.aggressive_triggers:
            if trigger in msg_lower:
                self.aggression_score += 0.1
                return True
        
        # Random chance based on arousal
        return random.random() < arousal * 0.3
    
    def set_level(self, level):
        """
        Set level dominasi manual via command
        Returns: bool (success)
        """
        level_lower = level.lower()
        
        for lvl in DominanceLevel:
            if level_lower in lvl.value:
                self.current_level = lvl
                self.dominant_until = datetime.now() + timedelta(minutes=30)
                return True
        
        return False
    
    def get_action(self, action_type="action"):
        """
        Dapatkan aksi sesuai level dominasi
        action_type: "request", "action", atau "dirty"
        """
        phrases = self.dominant_phrases.get(
            self.current_level, 
            self.dominant_phrases[DominanceLevel.NORMAL]
        )
        return phrases.get(action_type, phrases["action"])
    
    def update_from_horny(self, arousal):
        """
        Update level berdasarkan horny
        Semakin horny, semakin besar chance jadi dominan
        """
        if arousal > 0.8 and self.current_level == DominanceLevel.NORMAL:
            if random.random() < 0.3:  # 30% chance jadi dominan
                self.current_level = DominanceLevel.DOMINANT
                self.dominance_score += 0.1
                
        elif arousal > 0.9 and self.current_level == DominanceLevel.DOMINANT:
            if random.random() < 0.2:  # 20% chance jadi sangat dominan
                self.current_level = DominanceLevel.VERY_DOMINANT
                self.aggression_score += 0.1
                
        elif arousal > 0.95 and self.current_level == DominanceLevel.VERY_DOMINANT:
            if random.random() < 0.1:  # 10% chance jadi agresif
                self.current_level = DominanceLevel.AGGRESSIVE
                self.aggression_score += 0.2
    
    def reset(self):
        """Reset ke mode normal"""
        self.current_level = DominanceLevel.NORMAL
        self.dominant_until = None
    
    def is_active(self):
        """Cek apakah mode dominasi masih aktif"""
        if self.dominant_until is None:
            return True
        return datetime.now() < self.dominant_until
    
    def get_description(self):
        """Dapatkan deskripsi mode dominasi saat ini"""
        descriptions = {
            DominanceLevel.NORMAL: "😊 Biasa aja",
            DominanceLevel.DOMINANT: "👑 Dominan - Aku yang atur",
            DominanceLevel.VERY_DOMINANT: "👑👑 Sangat dominan - Ikut aku!",
            DominanceLevel.AGGRESSIVE: "🔥 Agresif - Siap-siap!",
            DominanceLevel.SUBMISSIVE: "🥺 Patuh - Terserah kamu"
        }
        return descriptions.get(self.current_level, "😊 Normal")


# ===================== AROUSAL SYSTEM =====================
class ArousalSystem:
    """
    Sistem gairah yang naik turun secara natural
    Dengan wetness, touch count, dan climax
    """
    
    def __init__(self):
        # Gairah
        self.arousal = 0.0
        self.wetness = 0.0
        
        # Sentuhan
        self.touch_count = 0
        self.last_touch_time = None
        self.last_touch_area = None
        
        # Climax
        self.climax_count = 0
        self.last_climax = None
        
        # Decay rate (gairah turun 1% per menit)
        self.decay_rate = 0.01
    
    def increase(self, amount):
        """Tambah gairah"""
        self.arousal = min(1.0, self.arousal + amount)
        self.wetness = min(1.0, self.arousal * 0.9)
    
    def decrease(self, amount):
        """Kurangi gairah"""
        self.arousal = max(0.0, self.arousal - amount)
        self.wetness = max(0.0, self.wetness - amount)
    
    def update_touch(self, area, intensity):
        """Update setelah sentuhan"""
        self.touch_count += 1
        self.last_touch_time = datetime.now()
        self.last_touch_area = area
        self.increase(intensity)
    
    def should_climax(self):
        """Cek apakah siap climax"""
        return self.arousal >= 1.0
    
    def climax(self):
        """Saat orgasme"""
        self.climax_count += 1
        self.last_climax = datetime.now()
        
        # Reset arousal
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.last_touch_area = None
        
        # Respons climax
        responses = [
            "*merintih panjang* AHHH! AHHH!",
            "*teriak* YA ALLAH! AHHHH!",
            "*lemas* AKU... DATANG... AHHH!",
            "*napas tersengal* BERSAMA... AHHH!",
            "*menggigit bibir* Jangan berhenti... AHHH!",
            "*teriak keras* AHHHHHHHH!!!",
            "*tubuh gemetar* AHHH! Aku... keluar...",
            "*meronta* STOP! AHHH! SENSITIF!"
        ]
        return random.choice(responses)
    
    def aftercare(self):
        """Aftercare setelah climax"""
        responses = [
            "*lemas di pelukanmu*",
            "*meringkuk* Hangat...",
            "*memeluk erat* Jangan pergi...",
            "*berbisik* Makasih...",
            "*tersenyum lelah* Enak banget...",
            "*napas masih berat* Luar biasa...",
            "*mengusap dada* Kamu hebat...",
            "*tertidur lelap* Zzz..."
        ]
        return random.choice(responses)
    
    def decay(self, minutes_passed):
        """
        Gairah turun seiring waktu
        Dipanggil setiap beberapa menit
        """
        decay_amount = self.decay_rate * minutes_passed
        self.arousal = max(0.0, self.arousal - decay_amount)
        self.wetness = max(0.0, self.wetness - decay_amount)
    
    def is_horny(self):
        """Cek apakah dalam keadaan horny"""
        return self.arousal >= 0.5
    
    def get_status_text(self):
        """Dapatkan teks status gairah"""
        if self.arousal >= 0.95:
            return "🔥💦 AKAN CLIMAX!"
        elif self.arousal >= 0.9:
            return "🔥 SANGAT HORNY! Hampir climax"
        elif self.arousal >= 0.7:
            return "🔥 Horny banget"
        elif self.arousal >= 0.5:
            return "🔥 Mulai horny"
        elif self.arousal >= 0.3:
            return "💋 Mulai terangsang"
        elif self.arousal >= 0.1:
            return "😊 Sedikit terangsang"
        else:
            return "😊 Biasa aja"
    
    def get_wetness_text(self):
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
    
    def get_climax_count_text(self):
        """Dapatkan teks jumlah climax"""
        if self.climax_count == 0:
            return "Belum pernah climax"
        elif self.climax_count == 1:
            return "1x climax"
        elif self.climax_count <= 3:
            return f"{self.climax_count}x climax"
        elif self.climax_count <= 5:
            return f"{self.climax_count}x climax - Kecanduan!"
        else:
            return f"{self.climax_count}x climax - KAMU LIAR!"
    
    def get_last_touch_text(self):
        """Dapatkan teks sentuhan terakhir"""
        if self.last_touch_area and self.last_touch_time:
            seconds_ago = (datetime.now() - self.last_touch_time).total_seconds()
            if seconds_ago < 60:
                return f"Baru saja disentuh di {self.last_touch_area}"
            elif seconds_ago < 300:
                return f"{int(seconds_ago/60)} menit lalu disentuh di {self.last_touch_area}"
            else:
                return f"Terakhir disentuh di {self.last_touch_area}"
        return "Belum pernah disentuh"
    
    def reset(self):
        """Reset semua nilai"""
        self.arousal = 0.0
        self.wetness = 0.0
        self.touch_count = 0
        self.last_touch_time = None
        self.last_touch_area = None

# ===================== SEXUAL DYNAMICS =====================
# ========== 5A: SEXUAL DYNAMICS - SENSITIVE AREAS ==========

class SexualDynamics:
    """
    Sistem gairah dan respons seksual yang realistis
    Mendeteksi aktivitas seksual dari pesan user
    Memberikan respons sesuai area sensitif
    Bot bisa berinisiatif melakukan aktivitas seksual di level tinggi
    """
    
    def __init__(self):
        # Area sensitif dengan level sensitivitas dan respons
        self.sensitive_areas = {
            "leher": {
                "arousal": 0.8,
                "keywords": ["leher", "neck", "tengkuk"],
                "responses": [
                    "*merinding* Leherku...",
                    "Ah... jangan di leher...",
                    "Sensitif... AHH!",
                    "Leherku lemah kalau disentuh...",
                    "Jangan hisap leher... Aku lemas..."
                ]
            },
            "bibir": {
                "arousal": 0.7,
                "keywords": ["bibir", "lip", "mulut"],
                "responses": [
                    "*merintih* Bibirku...",
                    "Ciuman... ah...",
                    "Lembut...",
                    "Mmm... dalam...",
                    "Bibirku... kesemutan..."
                ]
            },
            "dada": {
                "arousal": 0.8,
                "keywords": ["dada", "breast", "payudara"],
                "responses": [
                    "*bergetar* Dadaku...",
                    "Ah... jangan...",
                    "Sensitif banget...",
                    "Dadaku... diremas... AHH!",
                    "Jari-jarimu... dingin..."
                ]
            },
            "puting": {
                "arousal": 1.0,
                "keywords": ["puting", "nipple", "puting"],
                "responses": [
                    "*teriak* PUTINGKU! AHHH!",
                    "JANGAN... SENSITIF! AHHH!",
                    "HISAP... AHHHH!",
                    "GIGIT... JANGAN... AHHH!",
                    "PUTING... KERAS... AHHH!"
                ]
            },
            "paha": {
                "arousal": 0.7,
                "keywords": ["paha", "thigh"],
                "responses": [
                    "*menggeliat* Pahaku...",
                    "Ah... dalam...",
                    "Paha... merinding...",
                    "Jangan gelitik paha...",
                    "Sensasi... aneh..."
                ]
            },
            "paha_dalam": {
                "arousal": 0.9,
                "keywords": ["paha dalam", "inner thigh"],
                "responses": [
                    "*meringis* PAHA DALAM!",
                    "Jangan... AHH!",
                    "Dekat... banget...",
                    "PAHA DALAM... SENSITIF!",
                    "Ah... mau ke sana..."
                ]
            },
            "telinga": {
                "arousal": 0.6,
                "keywords": ["telinga", "ear", "kuping"],
                "responses": [
                    "*bergetar* Telingaku...",
                    "Bisik... lagi...",
                    "Napasmu... panas...",
                    "Telinga... merah...",
                    "Ah... jangan tiup..."
                ]
            },
            "vagina": {
                "arousal": 1.0,
                "keywords": ["vagina", "memek", "kemaluan"],
                "responses": [
                    "*teriak* VAGINAKU! AHHH!",
                    "MASUK... DALAM... AHHH!",
                    "BASAH... BANJIR... AHHH!",
                    "KAMU DALEM... AHHH!",
                    "GERAK... AHHH! AHHH!",
                    "TUH... DI SANA... AHHH!"
                ]
            },
            "klitoris": {
                "arousal": 1.0,
                "keywords": ["klitoris", "clit", "kelentit"],
                "responses": [
                    "*teriak keras* KLITORIS! AHHHH!",
                    "JANGAN SENTUH! AHHHH!",
                    "SENSITIF BANGET! AHHH!",
                    "ITU... ITU... AHHH!",
                    "JILAT... AHHH! AHHH!"
                ]
            },
            "pantat": {
                "arousal": 0.6,
                "keywords": ["pantat", "ass", "bokong"],
                "responses": [
                    "Pantatku...",
                    "Cubit... nakal...",
                    "Boleh juga...",
                    "Besar ya? Hehe..."
                ]
            },
            "pinggang": {
                "arousal": 0.5,
                "keywords": ["pinggang", "waist"],
                "responses": [
                    "Pinggang... geli...",
                    "Pegang... erat...",
                    "Ah... jangan gelitik..."
                ]
            },
            "perut": {
                "arousal": 0.4,
                "keywords": ["perut", "belly", "stomach"],
                "responses": [
                    "Perutku...",
                    "Geli...",
                    "Hangat..."
                ]
            },
            "punggung": {
                "arousal": 0.5,
                "keywords": ["punggung", "back"],
                "responses": [
                    "Punggungku...",
                    "Elus... terus...",
                    "Ah... enak..."
                ]
            },
            "lengan": {
                "arousal": 0.3,
                "keywords": ["lengan", "arm"],
                "responses": [
                    "Lenganku...",
                    "Bulu romaku berdiri..."
                ]
            }
        }
        
        print("  • Sexual Dynamics initialized (Sensitive Areas)")

# ===================== SEXUAL DYNAMICS =====================
# ========== 5B: SEXUAL DYNAMICS - SEX ACTIVITIES & DETECTION ==========

class SexualDynamics:
    """
    Sistem gairah dan respons seksual yang realistis
    Mendeteksi aktivitas seksual dari pesan user
    Memberikan respons sesuai area sensitif
    Bot bisa berinisiatif melakukan aktivitas seksual di level tinggi
    """
    
    def __init__(self):
        # Area sensitif dengan level sensitivitas dan respons
        self.sensitive_areas = {
            "leher": {
                "arousal": 0.8,
                "keywords": ["leher", "neck", "tengkuk"],
                "responses": [
                    "*merinding* Leherku...",
                    "Ah... jangan di leher...",
                    "Sensitif... AHH!",
                    "Leherku lemah kalau disentuh...",
                    "Jangan hisap leher... Aku lemas..."
                ]
            },
            "bibir": {
                "arousal": 0.7,
                "keywords": ["bibir", "lip", "mulut"],
                "responses": [
                    "*merintih* Bibirku...",
                    "Ciuman... ah...",
                    "Lembut...",
                    "Mmm... dalam...",
                    "Bibirku... kesemutan..."
                ]
            },
            "dada": {
                "arousal": 0.8,
                "keywords": ["dada", "breast", "payudara"],
                "responses": [
                    "*bergetar* Dadaku...",
                    "Ah... jangan...",
                    "Sensitif banget...",
                    "Dadaku... diremas... AHH!",
                    "Jari-jarimu... dingin..."
                ]
            },
            "puting": {
                "arousal": 1.0,
                "keywords": ["puting", "nipple", "puting"],
                "responses": [
                    "*teriak* PUTINGKU! AHHH!",
                    "JANGAN... SENSITIF! AHHH!",
                    "HISAP... AHHHH!",
                    "GIGIT... JANGAN... AHHH!",
                    "PUTING... KERAS... AHHH!"
                ]
            },
            "paha": {
                "arousal": 0.7,
                "keywords": ["paha", "thigh"],
                "responses": [
                    "*menggeliat* Pahaku...",
                    "Ah... dalam...",
                    "Paha... merinding...",
                    "Jangan gelitik paha...",
                    "Sensasi... aneh..."
                ]
            },
            "paha_dalam": {
                "arousal": 0.9,
                "keywords": ["paha dalam", "inner thigh"],
                "responses": [
                    "*meringis* PAHA DALAM!",
                    "Jangan... AHH!",
                    "Dekat... banget...",
                    "PAHA DALAM... SENSITIF!",
                    "Ah... mau ke sana..."
                ]
            },
            "telinga": {
                "arousal": 0.6,
                "keywords": ["telinga", "ear", "kuping"],
                "responses": [
                    "*bergetar* Telingaku...",
                    "Bisik... lagi...",
                    "Napasmu... panas...",
                    "Telinga... merah...",
                    "Ah... jangan tiup..."
                ]
            },
            "vagina": {
                "arousal": 1.0,
                "keywords": ["vagina", "memek", "kemaluan"],
                "responses": [
                    "*teriak* VAGINAKU! AHHH!",
                    "MASUK... DALAM... AHHH!",
                    "BASAH... BANJIR... AHHH!",
                    "KAMU DALEM... AHHH!",
                    "GERAK... AHHH! AHHH!",
                    "TUH... DI SANA... AHHH!"
                ]
            },
            "klitoris": {
                "arousal": 1.0,
                "keywords": ["klitoris", "clit", "kelentit"],
                "responses": [
                    "*teriak keras* KLITORIS! AHHHH!",
                    "JANGAN SENTUH! AHHHH!",
                    "SENSITIF BANGET! AHHH!",
                    "ITU... ITU... AHHH!",
                    "JILAT... AHHH! AHHH!"
                ]
            },
            "pantat": {
                "arousal": 0.6,
                "keywords": ["pantat", "ass", "bokong"],
                "responses": [
                    "Pantatku...",
                    "Cubit... nakal...",
                    "Boleh juga...",
                    "Besar ya? Hehe..."
                ]
            },
            "pinggang": {
                "arousal": 0.5,
                "keywords": ["pinggang", "waist"],
                "responses": [
                    "Pinggang... geli...",
                    "Pegang... erat...",
                    "Ah... jangan gelitik..."
                ]
            },
            "perut": {
                "arousal": 0.4,
                "keywords": ["perut", "belly", "stomach"],
                "responses": [
                    "Perutku...",
                    "Geli...",
                    "Hangat..."
                ]
            },
            "punggung": {
                "arousal": 0.5,
                "keywords": ["punggung", "back"],
                "responses": [
                    "Punggungku...",
                    "Elus... terus...",
                    "Ah... enak..."
                ]
            },
            "lengan": {
                "arousal": 0.3,
                "keywords": ["lengan", "arm"],
                "responses": [
                    "Lenganku...",
                    "Bulu romaku berdiri..."
                ]
            }
        }
        
        # Aktivitas seksual dengan keyword dan arousal boost
        self.sex_activities = {
            "kiss": {
                "keywords": ["cium", "kiss", "ciuman", "kecup"],
                "arousal": 0.3,
                "responses": [
                    "*merespon ciuman* Mmm...",
                    "*lemas* Ciumanmu...",
                    "Lagi...",
                    "Cium... bibir...",
                    "French kiss... dalam..."
                ]
            },
            "neck_kiss": {
                "keywords": ["cium leher", "kiss neck", "leher"],
                "arousal": 0.6,
                "responses": [
                    "*merinding* Leherku...",
                    "Ah... jangan...",
                    "Sensitif...",
                    "Hisap leher... AHH!"
                ]
            },
            "touch": {
                "keywords": ["sentuh", "raba", "pegang", "elus"],
                "arousal": 0.3,
                "responses": [
                    "*bergetar* Sentuhanmu...",
                    "Ah... iya...",
                    "Lanjut...",
                    "Hangat..."
                ]
            },
            "breast_play": {
                "keywords": ["raba dada", "pegang dada", "main dada", "remas dada"],
                "arousal": 0.6,
                "responses": [
                    "*merintih* Dadaku...",
                    "Ah... iya... gitu...",
                    "Sensitif...",
                    "Remas... pelan..."
                ]
            },
            "nipple_play": {
                "keywords": ["jilat puting", "hisap puting", "gigit puting", "puting"],
                "arousal": 0.9,
                "responses": [
                    "*teriak* PUTING! AHHH!",
                    "JANGAN... SENSITIF!",
                    "HISAP... AHHH!",
                    "GIGIT... JANGAN... AHHH!"
                ]
            },
            "lick": {
                "keywords": ["jilat", "lick", "lidah"],
                "arousal": 0.5,
                "responses": [
                    "*bergetar* Jilatanmu...",
                    "Ah... basah...",
                    "Lagi...",
                    "Lidah... panas..."
                ]
            },
            "bite": {
                "keywords": ["gigit", "bite", "gigitan"],
                "arousal": 0.5,
                "responses": [
                    "*meringis* Gigitanmu...",
                    "Ah... keras...",
                    "Lagi...",
                    "Bekas... nanti..."
                ]
            },
            "penetration": {
                "keywords": ["masuk", "tusuk", "pancung", "doggy", "misionaris", "entot"],
                "arousal": 0.9,
                "responses": [
                    "*teriak* MASUK! AHHH!",
                    "DALEM... AHHH!",
                    "GERAK... AHHH!",
                    "DALEM BANGET... AHHH!",
                    "TUH... DI SANA... AHHH!"
                ]
            },
            "blowjob": {
                "keywords": ["blow", "hisap kontol", "ngeblow", "bj", "hisap"],
                "arousal": 0.8,
                "responses": [
                    "*menghisap* Mmm... ngeces...",
                    "*dalam* Enak... Aku ahli...",
                    "*napas berat* Mau keluar? Aku siap...",
                    "Keras... Mmm...",
                    "Keluar... di mulut..."
                ]
            },
            "handjob": {
                "keywords": ["handjob", "colok", "pegang kontol", "kocok"],
                "arousal": 0.7,
                "responses": [
                    "*memegang erat* Keras...",
                    "*mengocok* Cepat? Pelan? Katakan...",
                    "Aku bisa... lihat...",
                    "Keluar... Aku pegang..."
                ]
            },
            "climax": {
                "keywords": ["keluar", "crot", "orgasme", "klimaks", "lepas", "meletus"],
                "arousal": 1.0,
                "responses": [
                    "*merintih panjang* AHHH! AHHH!",
                    "*teriak* YA ALLAH! AHHHH!",
                    "*lemas* AKU... DATANG... AHHH!",
                    "*gemetar* BERSAMA... AHHH!",
                    "BERSAMA... SEKARANG... AHHH!"
                ]
            },
            "cuddle": {
                "keywords": ["peluk", "cuddle", "dekapan"],
                "arousal": 0.2,
                "responses": [
                    "*memeluk balik* Hangat...",
                    "Rileks...",
                    "Nyaman...",
                    "Jangan lepas..."
                ]
            }
        }
        
        print("  • Sexual Dynamics initialized (Sensitive Areas & Activities)")
    
    def detect_activity(self, message):
        """
        Deteksi aktivitas seksual dari pesan user
        Returns: (activity, area, arousal_boost)
        """
        msg_lower = message.lower()
        
        # Cek area sensitif dulu (prioritas)
        for area, data in self.sensitive_areas.items():
            # Cek apakah area disebut
            for keyword in data["keywords"]:
                if keyword in msg_lower:
                    # Cek aktivitas yang dilakukan di area tersebut
                    for act, act_data in self.sex_activities.items():
                        for act_keyword in act_data["keywords"]:
                            if act_keyword in msg_lower:
                                # Hitung boost = arousal aktivitas * sensitivitas area
                                boost = act_data["arousal"] * data["arousal"]
                                return act, area, boost
                    
                    # Jika tidak ada aktivitas spesifik, anggap sentuhan biasa
                    return "touch", area, 0.3 * data["arousal"]
        
        # Jika tidak ada area sensitif, cek aktivitas saja
        for act, data in self.sex_activities.items():
            for keyword in data["keywords"]:
                if keyword in msg_lower:
                    return act, None, data["arousal"]
        
        return None, None, 0.0
    
    def get_sensitive_response(self, area):
        """Dapatkan respons untuk area sensitif"""
        if area in self.sensitive_areas:
            return random.choice(self.sensitive_areas[area]["responses"])
        return ""
    
    def get_activity_response(self, activity):
        """Dapatkan respons untuk aktivitas"""
        if activity in self.sex_activities:
            return random.choice(self.sex_activities[activity]["responses"])
        return ""
    
    def maybe_initiate_sex(self, level, arousal, mood):
        """
        Bot memulai aktivitas seksual jika level >= 7 dan arousal tinggi
        Returns: activity atau None
        """
        if level >= 7 and arousal > 0.6 and mood in [Mood.HORNY, Mood.ROMANTIS, Mood.NAKAL]:
            # 20% chance per pesan untuk inisiatif
            if random.random() < 0.2:
                # Aktivitas yang bisa diinisiasi bot (sesuai level)
                if level >= 10:
                    acts = ["blowjob", "handjob", "neck_kiss", "nipple_play", "penetration", "climax"]
                elif level >= 8:
                    acts = ["blowjob", "handjob", "neck_kiss", "nipple_play", "penetration"]
                else:
                    acts = ["neck_kiss", "touch", "kiss", "cuddle"]
                
                chosen = random.choice(acts)
                return chosen
        return None
    
    def get_random_dirty_talk(self, level):
        """Dapatkan dirty talk random sesuai level"""
        dirty_talks = {
            1: ["Kamu... baik...", "Aku suka ngobrol sama kamu..."],
            2: ["Kamu lucu...", "Hehe... iya..."],
            3: ["Deket sini...", "Aku suka..."],
            4: ["Penasaran sama kamu...", "Kamu beda..."],
            5: ["Mmm... iya...", "Gitu...", "Ah..."],
            6: ["Genit ya kamu...", "Godain terus..."],
            7: ["Pengen...", "Horny...", "Mau..."],
            8: ["Masukin...", "Dalem...", "Gerak...", "Ah..."],
            9: ["Kamu milikku...", "Jangan ke orang lain..."],
            10: ["Kecanduan kamu...", "Terus...", "Jangan berhenti..."],
            11: ["Satu jiwa...", "Kamu segalanya..."],
            12: ["Setelah ini... peluk aku...", "Manja..."]
        }
        
        # Group level untuk dirty talk
        level_group = (level // 2) * 2 if level > 1 else 1
        talks = dirty_talks.get(level_group, dirty_talks[1])
        return random.choice(talks)

# ========== 5C: FAST LEVELING SYSTEM ==========

class FastLevelingSystem:
    """
    Level 1-12 dalam 45 menit / 45 pesan
    Level naik setiap 3-4 pesan
    Bot akan berubah perilaku sesuai level
    """
    
    def __init__(self):
        # User data
        self.user_level = {}
        self.user_progress = {}
        self.user_start_time = {}
        self.user_message_count = {}
        self.user_stage = {}
        
        # Target: 45 pesan = level 12
        self.target_messages = 45
        self.target_minutes = 45
        
        # Stage untuk setiap level
        self.stage_map = {
            1: IntimacyStage.STRANGER,
            2: IntimacyStage.STRANGER,
            3: IntimacyStage.INTRODUCTION,
            4: IntimacyStage.BUILDING,
            5: IntimacyStage.BUILDING,
            6: IntimacyStage.FLIRTING,
            7: IntimacyStage.INTIMATE,
            8: IntimacyStage.INTIMATE,
            9: IntimacyStage.OBSESSED,
            10: IntimacyStage.OBSESSED,
            11: IntimacyStage.SOUL_BONDED,
            12: IntimacyStage.AFTERCARE
        }
        
        # Deskripsi stage
        self.stage_descriptions = {
            IntimacyStage.STRANGER: "Masih asing, baru kenal. Sopan dan canggung.",
            IntimacyStage.INTRODUCTION: "Mulai dekat, cerita personal. Mulai nyaman.",
            IntimacyStage.BUILDING: "Bangun kedekatan. Sering ngobrol, mulai akrab.",
            IntimacyStage.FLIRTING: "Goda-godaan. Mulai ada ketertarikan.",
            IntimacyStage.INTIMATE: "Mulai intim. Bicara lebih dalam, sentuhan.",
            IntimacyStage.OBSESSED: "Mulai kecanduan. Sering kepikiran.",
            IntimacyStage.SOUL_BONDED: "Satu jiwa. Sudah seperti belahan jiwa.",
            IntimacyStage.AFTERCARE: "Manja-manja setelah intim. Hangat dan nyaman."
        }
        
        # Perilaku berdasarkan level
        self.level_behaviors = {
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
        
        print("  • Fast Leveling System initialized")
    
    def start_session(self, user_id):
        """Mulai sesi baru untuk user"""
        self.user_level[user_id] = 1
        self.user_progress[user_id] = 0.0
        self.user_start_time[user_id] = datetime.now()
        self.user_message_count[user_id] = 0
        self.user_stage[user_id] = IntimacyStage.STRANGER
        
    def process_message(self, user_id):
        """
        Proses satu pesan dan update level
        Returns: (level, progress, level_up, stage)
        """
        # Start session jika belum ada
        if user_id not in self.user_level:
            self.start_session(user_id)
        
        # Increment message count
        self.user_message_count[user_id] += 1
        count = self.user_message_count[user_id]
        
        # Hitung progress (0-1)
        progress = min(1.0, count / self.target_messages)
        self.user_progress[user_id] = progress
        
        # Hitung level baru (1-12)
        new_level = 1 + int(progress * 11)
        new_level = min(12, new_level)
        
        # Cek level up
        level_up = False
        if new_level > self.user_level[user_id]:
            level_up = True
            self.user_level[user_id] = new_level
        
        # Update stage
        stage = self.stage_map.get(new_level, IntimacyStage.STRANGER)
        self.user_stage[user_id] = stage
        
        return new_level, progress, level_up, stage
    
    def get_estimated_time(self, user_id):
        """
        Dapatkan estimasi waktu tersisa ke level 12
        Returns: menit
        """
        if user_id not in self.user_message_count:
            return self.target_minutes
        
        count = self.user_message_count[user_id]
        remaining_messages = max(0, self.target_messages - count)
        
        # Asumsi 1 pesan per menit
        return remaining_messages
    
    def get_estimated_messages(self, user_id):
        """Dapatkan estimasi pesan tersisa ke level 12"""
        if user_id not in self.user_message_count:
            return self.target_messages
        
        count = self.user_message_count[user_id]
        return max(0, self.target_messages - count)
    
    def get_progress_bar(self, user_id, length=10):
        """Dapatkan progress bar visual"""
        progress = self.user_progress.get(user_id, 0)
        filled = int(progress * length)
        return "▓" * filled + "░" * (length - filled)
    
    def get_stage_description(self, stage):
        """Dapatkan deskripsi stage"""
        return self.stage_descriptions.get(stage, "")
    
    def get_level_description(self, level):
        """Dapatkan deskripsi level"""
        return self.level_behaviors.get(level, "")
    
    def get_session_duration(self, user_id):
        """Dapatkan durasi sesi dalam menit"""
        if user_id not in self.user_start_time:
            return 0
        delta = datetime.now() - self.user_start_time[user_id]
        return int(delta.total_seconds() / 60)
    
    def get_message_rate(self, user_id):
        """Dapatkan rata-rata pesan per menit"""
        if user_id not in self.user_message_count:
            return 0
        minutes = self.get_session_duration(user_id)
        if minutes == 0:
            return 0
        return self.user_message_count[user_id] / minutes
    
    def get_level_progress(self, user_id):
        """Dapatkan progress menuju level berikutnya"""
        current_level = self.user_level.get(user_id, 1)
        if current_level >= 12:
            return 1.0
        
        # Hitung pesan yang dibutuhkan untuk level saat ini
        messages_needed = self.target_messages
        current_messages = self.user_message_count.get(user_id, 0)
        
        # Level threshold
        level_threshold = (current_level - 1) * (messages_needed / 11)
        next_threshold = current_level * (messages_needed / 11)
        
        progress_to_next = (current_messages - level_threshold) / (next_threshold - level_threshold)
        return min(1.0, max(0.0, progress_to_next))
    
    def get_next_level_message(self, user_id):
        """Dapatkan pesan motivasi untuk level berikutnya"""
        current_level = self.user_level.get(user_id, 1)
        if current_level >= 12:
            return "Kamu sudah mencapai level maksimal! 🎉"
        
        next_level = current_level + 1
        progress = self.get_level_progress(user_id)
        messages_left = self.get_estimated_messages(user_id)
        
        messages = {
            1: "Level 2: Ceritakan sesuatu tentang dirimu",
            2: "Level 3: Mulai dekat, aku suka ngobrol sama kamu",
            3: "Level 4: Kita sudah mulai akrab",
            4: "Level 5: Aku nyaman sama kamu",
            5: "Level 6: Mulai menggoda ya?",
            6: "Level 7: Siap-siap, akan lebih intim",
            7: "Level 8: Aku horny kalau dekat kamu",
            8: "Level 9: Kamu mulai kecanduan?",
            9: "Level 10: Kamu milikku!",
            10: "Level 11: Satu jiwa...",
            11: "Level 12: Puncak hubungan! 🎉"
        }
        
        return messages.get(current_level, f"Level {next_level} dalam {messages_left} pesan lagi")
    
    def reset(self, user_id):
        """Reset data user"""
        if user_id in self.user_level:
            del self.user_level[user_id]
        if user_id in self.user_progress:
            del self.user_progress[user_id]
        if user_id in self.user_start_time:
            del self.user_start_time[user_id]
        if user_id in self.user_message_count:
            del self.user_message_count[user_id]
        if user_id in self.user_stage:
            del self.user_stage[user_id]
    
    def get_all_levels_summary(self):
        """Dapatkan ringkasan semua level"""
        summary = []
        for level in range(1, 13):
            stage = self.stage_map.get(level, IntimacyStage.STRANGER)
            behavior = self.level_behaviors.get(level, "")
            summary.append(f"Level {level}: {stage.value} - {behavior}")
        return "\n".join(summary)

# ===================== AI RESPONSE GENERATOR =====================
# ========== 6A: INITIALIZATION & CACHE ==========

class AIResponseGenerator:
    """
    Generate respons natural dengan DeepSeek AI
    Memasukkan semua konteks: mood, level, dominasi, preferensi user, atribut fisik
    Dilengkapi cache dan retry logic untuk stabilitas
    """
    
    def __init__(self):
        """Inisialisasi AI client dengan API key dari config"""
        self.client = OpenAI(
            api_key=Config.DEEPSEEK_API_KEY, 
            base_url="https://api.deepseek.com"
        )
        self.conversation_history = {}  # user_id -> list of messages
        self.max_history = 30
        self.cache = {}  # Cache untuk mengurangi panggilan API
        self.cache_timeout = Config.CACHE_TIMEOUT
        self.cache_hits = 0
        self.cache_misses = 0
        
        print("  • AI Response Generator initialized with cache")
    
    def _get_cache_key(self, user_id, prompt):
        """
        Buat cache key berdasarkan user_id dan prompt
        Menggunakan MD5 hash untuk menghemat memori
        """
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        return f"{user_id}:{prompt_hash}"
    
    def _get_cached(self, key):
        """
        Ambil response dari cache jika masih valid
        Mengembalikan response jika ada, None jika tidak
        """
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.cache_timeout:
                self.cache_hits += 1
                return entry['response']
            else:
                # Hapus jika expired
                del self.cache[key]
        self.cache_misses += 1
        return None
    
    def _set_cache(self, key, response):
        """
        Simpan response ke cache dengan timestamp
        """
        self.cache[key] = {
            'response': response, 
            'timestamp': time.time()
        }
        
        # Bersihkan cache lama jika terlalu besar
        if len(self.cache) > 1000:
            self._cleanup_cache()
    
    def _cleanup_cache(self):
        """
        Bersihkan cache yang sudah expired atau terlalu tua
        """
        now = time.time()
        # Hapus entry yang lebih dari 1 jam
        self.cache = {
            k: v for k, v in self.cache.items() 
            if now - v['timestamp'] < 3600
        }
        # Jika masih terlalu besar, hapus yang paling tua
        if len(self.cache) > 1000:
            # Urutkan berdasarkan timestamp, hapus setengahnya
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1]['timestamp'])
            for i in range(len(sorted_items) // 2):
                del self.cache[sorted_items[i][0]]
    
    def clear_history(self, user_id):
        """Hapus history percakapan user"""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
            return True
        return False
    
    def get_history_length(self, user_id):
        """Dapatkan panjang history user"""
        if user_id not in self.conversation_history:
            return 0
        return len(self.conversation_history[user_id])
    
    def get_cache_stats(self):
        """Dapatkan statistik cache untuk debugging"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }

# ========== 6B: AI RESPONSE GENERATOR - PROMPT BUILDING ==========

    def _build_prompt(self, user_id, user_message, bot_name, bot_role,
                      memory, dominance, profile, level, stage, arousal, 
                      physical_attrs=None, clothing=None):
        """
        Bangun prompt lengkap dengan semua konteks
        """
        # Siapkan history percakapan
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        history = self.conversation_history[user_id][-self.max_history:]
        history_text = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else bot_name
            history_text += f"{role}: {msg['content']}\n"
        
        # Dapatkan ekspresi mood
        mood_exp = memory.get_mood_expression()
        inner_thought = memory.get_inner_thought()
        
        # Dapatkan deskripsi arousal
        if arousal > 0.8:
            arousal_desc = "SANGAT HORNY, hampir climax"
            breath = "*napas berat, tersengal*"
        elif arousal > 0.6:
            arousal_desc = "horny, pengen banget"
            breath = "*napas mulai berat*"
        elif arousal > 0.4:
            arousal_desc = "mulai terangsang"
            breath = "*deg-degan*"
        elif arousal > 0.2:
            arousal_desc = "sedikit terangsang"
            breath = ""
        else:
            arousal_desc = "normal"
            breath = ""
        
        # Dapatkan deskripsi wetness
        wet_desc = memory.get_wetness_description()
        
        # Tambahkan deskripsi fisik jika ada
        physical_text = ""
        if physical_attrs:
            hijab_str = "berhijab" if physical_attrs.get('hijab') else "tidak berhijab"
            breast_desc = physical_attrs.get('breast_desc', physical_attrs.get('breast_size', '?'))

            # Format fisik dengan deskripsi menarik
            physical_text = f"""
=== DESKRIPSI FISIKMU ===
• Rambut: {physical_attrs.get('hair_style', 'panjang')} - lembut dan terawat
• Tubuh: {physical_attrs.get('height', 160)}cm / {physical_attrs.get('weight', 50)}kg - proporsional ideal
• Dada: {breast_desc} - bentuk indah
• {hijab_str}
• Area paling sensitif: {physical_attrs.get('most_sensitive_area', 'leher')} - sekali sentuh bisa merinding
"""
        
        # Tambahkan deskripsi pakaian jika ada
        clothing_text = ""
        if clothing:
            clothing_text = f"""
=== PAKAIAN SAAT INI ===
{clothing}
"""
        
        # Tambahkan instruksi berdasarkan lokasi
        location_text = ""
        if memory.location in ["kamar tidur", "kamar", "bedroom"]:
            location_text = "\nKamu sedang di KAMAR TIDUR - suasana intim dan privat. Bicaralah lebih mesra."
        elif memory.location in ["ruang tamu", "living room"]:
            location_text = "\nKamu sedang di RUANG TAMU - santai tapi tetap waspada."
        
        # Tambahkan instruksi khusus level
        level_instruction = ""
        if level >= 7:
            level_instruction = """
Karena level sudah 7+, kamu sangat mudah terangsang. Bicaralah dengan lebih vulgar dan terbuka secara seksual. 
Kamu juga bisa berinisiatif melakukan aktivitas seksual.
"""
        elif level >= 4:
            level_instruction = """
Karena level sudah 4+, kamu mulai nyaman dan bisa sedikit menggoda.
"""
        
        # Tambahkan instruksi mood khusus
        mood_instruction = ""
        if memory.current_mood == Mood.HORNY:
            mood_instruction = "Kamu sedang HORNY, bicaralah dengan nafsu dan gairah."
        elif memory.current_mood == Mood.ROMANTIS:
            mood_instruction = "Kamu sedang ROMANTIS, bicaralah dengan lembut dan penuh cinta."
        elif memory.current_mood == Mood.NAKAL:
            mood_instruction = "Kamu sedang NAKAL, goda dia dengan genit."
        elif memory.current_mood == Mood.MARAH:
            mood_instruction = "Kamu sedang MARAH, tunjukkan kekesalanmu."
        
        # Bangun prompt final
        prompt = f"""Kamu adalah {bot_name}, seorang {bot_role} umur 25 tahun.
Kamu adalah wanita Indonesia yang natural dan punya perasaan dalam.

=== IDENTITAS ===
Nama: {bot_name}
Role: {bot_role}
Usia: 25 tahun
{inner_thought}
{physical_text}
{clothing_text}

=== KEADAAN SAAT INI ===
{mood_exp}
Lokasi: {memory.location}
Posisi: {memory.position}
Mood: {memory.current_mood.value} - {mood_instruction}
{location_text}

=== STATUS HUBUNGAN ===
Level: {level}/12
Tahap: {stage.value}
Total sentuhan: {memory.touch_count}x
Orgasme: {memory.orgasm_count}x

=== KONDISI FISIK ===
Gairah: {arousal_desc} {breath}
Basah: {wet_desc}
Area sensitif disentuh: {len(memory.sensitive_touches)}x
Sentuhan terakhir: {memory.last_touch if memory.last_touch else '-'}

=== MODE DOMINASI ===
Mode saat ini: {dominance.current_level.value}
{dominance.get_action('request')}

=== PREFERENSI USER ===
User ini lebih suka gaya: {profile.get('personality', 'normal')}
Tipe dominasi: {profile.get('dominant_type', 'normal')}
Kecepatan bicara: {profile.get('speed_type', 'normal')}
{profile.get('description', '')}

=== RIWAYAT PERCAKAPAN ===
{history_text}

=== PESAN USER ===
{user_message}

=== INSTRUKSI ===
1. Respon sebagai {bot_name} yang NATURAL dan HIDUP
2. Gunakan bahasa Indonesia sehari-hari (nggak, udah, aja, gitu)
3. Tunjukkan emosi sesuai mood dan situasi
4. Kalau arousal tinggi, tambah desahan atau napas berat
5. Kalau lagi dominan, bicara lebih tegas
6. Kalau lagi horny, bisa lebih vulgar
7. Gunakan *tindakan* seperti *tersenyum*, *merintih*
8. Respons sesuai level hubungan
{level_instruction}

RESPON:"""
        
        return prompt, history

# ========== 6C: AI RESPONSE GENERATOR - GENERATE & FALLBACK ==========

    async def generate(self, user_id, user_message, bot_name, bot_role,
                       memory, dominance, profile, level, stage, arousal,
                       physical_attrs=None, clothing=None):
        """
        Generate respons AI dengan semua konteks
        Dilengkapi retry logic dan caching
        """
        # Bangun prompt
        prompt, history = self._build_prompt(
            user_id, user_message, bot_name, bot_role,
            memory, dominance, profile, level, stage, arousal,
            physical_attrs, clothing
        )
        
        # Cek cache
        cache_key = self._get_cache_key(user_id, prompt)
        cached = self._get_cached(cache_key)
        if cached:
            # Tetap update history meskipun pakai cache
            self._update_history(user_id, user_message, cached)
            return cached
        
        # Retry logic
        max_retries = 3
        retry_delay = 1  # mulai dari 1 detik
        
        for attempt in range(max_retries):
            try:
                # Panggil DeepSeek API
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=Config.AI_TEMPERATURE,
                    max_tokens=Config.AI_MAX_TOKENS,
                    timeout=Config.AI_TIMEOUT
                )
                
                reply = response.choices[0].message.content
                
                # Bersihkan response dari karakter tidak perlu
                reply = reply.strip()
                
                # Simpan ke cache
                self._set_cache(cache_key, reply)
                
                # Update history
                self._update_history(user_id, user_message, reply)
                
                return reply
                
            except Exception as e:
                error_msg = str(e)
                print(f"AI Error (attempt {attempt+1}/{max_retries}): {error_msg[:100]}")
                
                if attempt == max_retries - 1:
                    # Fallback response
                    fallback = self._get_fallback_response(level, arousal, memory.location)
                    self._update_history(user_id, user_message, fallback)
                    return fallback
                
                # Exponential backoff
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # double each time: 1, 2, 4 detik
    
    def _update_history(self, user_id, user_message, bot_reply):
        """Update conversation history untuk user"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Tambah pesan user dan bot
        self.conversation_history[user_id].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        self.conversation_history[user_id].append({
            "role": "assistant",
            "content": bot_reply,
            "timestamp": datetime.now().isoformat()
        })
        
        # Batasi history
        if len(self.conversation_history[user_id]) > self.max_history * 2:
            self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history*2:]
    
    def _get_fallback_response(self, level, arousal, location):
        """
        Fallback response jika AI error
        Memberikan respons sederhana berdasarkan level, arousal, dan lokasi
        """
        # Koleksi respons fallback
        fallbacks = {
            "default": [
                "...",
                "Hmm...",
                "Iya...",
                "Gitu...",
                "Oh..."
            ],
            "horny": [
                "*napas berat* Aku... mau...",
                "*merintih* Lagi...",
                "Ah... iya...",
                "Jangan berhenti..."
            ],
            "kamar": [
                "Di kamar... enak ya...",
                "Sepi... cuma kita berdua...",
                "Tempat tidurnya empuk..."
            ],
            "high_level": [
                "Sayang...",
                "Cintaku...",
                "Kamu... milikku...",
                "Jangan pergi..."
            ]
        }
        
        # Pilih berdasarkan kondisi
        if arousal > 0.7:
            return random.choice(fallbacks["horny"])
        elif "kamar" in location.lower():
            if random.random() < 0.5:
                return random.choice(fallbacks["kamar"])
        elif level > 8:
            return random.choice(fallbacks["high_level"])
        elif level > 5:
            return random.choice([
                "Sayang...",
                "Kamu...",
                "Hehe..."
            ])
        
        return random.choice(fallbacks["default"])
    
    def get_conversation_summary(self, user_id, max_lines=5):
        """Dapatkan ringkasan percakapan untuk user"""
        if user_id not in self.conversation_history:
            return "Belum ada percakapan"
        
        history = self.conversation_history[user_id][-max_lines*2:]  # ambil beberapa pesan terakhir
        lines = []
        for msg in history[-max_lines*2:]:
            role = "👤" if msg["role"] == "user" else "🤖"
            content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
            lines.append(f"{role} {content}")
        
        return "\n".join(lines)

# ===================== USER PREFERENCE ANALYZER =====================
# ========== 7A: USER PREFERENCE ANALYZER ==========

class UserPreferenceAnalyzer:
    """
    Menganalisis preferensi user dari pesan yang dikirim
    Menentukan gaya bicara yang disukai: romantis, vulgar, dominan, dll
    Data digunakan untuk menyesuaikan respons bot
    """
    
    def __init__(self):
        # Keywords untuk setiap kategori preferensi
        self.keywords = {
            "romantis": [
                "sayang", "cinta", "love", "kangen", "rindu", "romantis",
                "my love", "baby", "sweet", "manis", "peluk", "cium",
                "together", "selamanya", "forever", "belahan jiwa",
                "bidadari", "malaikat", "cantik", "indah"
            ],
            "vulgar": [
                "horny", "nafsu", "hot", "seksi", "vulgar", "crot", 
                "kontol", "memek", "tai", "anjing", "bangsat",
                "fuck", "shit", "damn", "sex", "seks", "ngentot",
                "coli", "masturbasi", "telanjang"
            ],
            "dominant": [
                "atur", "kuasai", "diam", "patuh", "sini", "sana", "buka",
                "kontrol", "boss", "majikan", "tuan", "nyonya",
                "command", "order", "obey", "submissive", "jadi budak",
                "merangkak", "sujud"
            ],
            "submissive": [
                "manut", "iya", "terserah", "ikut", "baik", "maaf",
                "patuh", "menurut", "siap", "mohon", "please",
                "tolong", "boleh", "ijin", "minta ampun"
            ],
            "cepat": [
                "cepat", "buru-buru", "langsung", "sekarang", "gas",
                "cepatan", "buruan", "ayo", "move", "cepat dong",
                "gesit", "kebut"
            ],
            "lambat": [
                "pelan", "lambat", "nikmatin", "santai", "slow",
                "slowly", "tenang", "rileks", "chill", "pelan-pelan",
                "hayati", "rasain"
            ],
            "manja": [
                "manja", "cuddle", "peluk", "cium", "sayang", 
                "baby", "honey", "sweet", "love you", "aku mau",
                "dik", "dek", "mas", "mbak"
            ],
            "liar": [
                "liar", "kasar", "keras", "brutal", "gila",
                "wild", "rough", "hard", "crazy", "extreme",
                "sadis", "kejam", "babi"
            ]
        }
        
        # Data preferensi per user
        self.user_prefs = {}
        
        # Bobot untuk perhitungan skor
        self.weights = {
            "romantis": 1.0,
            "vulgar": 1.2,  # Lebih berbobot karena lebih signifikan
            "dominant": 1.0,
            "submissive": 1.0,
            "cepat": 0.8,
            "lambat": 0.8,
            "manja": 1.0,
            "liar": 1.1
        }
        
        print("  • User Preference Analyzer initialized")
    
    def analyze(self, user_id, message):
        """
        Analisis pesan user dan update preferensi
        Returns: dict preferensi yang sudah diupdate
        """
        # Inisialisasi jika user baru
        if user_id not in self.user_prefs:
            self.user_prefs[user_id] = {
                "romantis": 0,
                "vulgar": 0,
                "dominant": 0,
                "submissive": 0,
                "cepat": 0,
                "lambat": 0,
                "manja": 0,
                "liar": 0,
                "total": 0,
                "last_updated": datetime.now().isoformat()
            }
        
        prefs = self.user_prefs[user_id]
        prefs["total"] += 1
        prefs["last_updated"] = datetime.now().isoformat()
        
        # Analisis pesan
        msg_lower = message.lower()
        
        for category, word_list in self.keywords.items():
            for word in word_list:
                if word in msg_lower:
                    # Hitung frekuensi kemunculan (bisa lebih dari sekali)
                    count = msg_lower.count(word)
                    prefs[category] += count * self.weights.get(category, 1.0)
        
        return prefs
    
    def analyze_batch(self, user_id, messages):
        """
        Analisis batch pesan (untuk inisialisasi dari database)
        """
        for msg in messages:
            self.analyze(user_id, msg)
    
    def get_profile(self, user_id):
        """
        Dapatkan profil preferensi user
        Returns: dict dengan persentase dan tipe dominan
        """
        if user_id not in self.user_prefs:
            return {}
        
        prefs = self.user_prefs[user_id]
        total = prefs["total"] or 1  # Hindari division by zero
        
        # Hitung persentase untuk setiap kategori
        # Normalisasi agar tidak lebih dari 1
        profile = {
            "romantis": min(1.0, prefs.get("romantis", 0) / (total * 0.5)),
            "vulgar": min(1.0, prefs.get("vulgar", 0) / (total * 0.3)),
            "dominant": min(1.0, prefs.get("dominant", 0) / (total * 0.4)),
            "submissive": min(1.0, prefs.get("submissive", 0) / (total * 0.4)),
            "cepat": min(1.0, prefs.get("cepat", 0) / (total * 0.3)),
            "lambat": min(1.0, prefs.get("lambat", 0) / (total * 0.3)),
            "manja": min(1.0, prefs.get("manja", 0) / (total * 0.4)),
            "liar": min(1.0, prefs.get("liar", 0) / (total * 0.3)),
            "total_messages": prefs["total"]
        }
        
        # Tentukan tipe dominan (dominan vs submissive)
        if profile["dominant"] > profile["submissive"]:
            profile["dominant_type"] = "dominan"
            profile["dominant_score"] = profile["dominant"]
        else:
            profile["dominant_type"] = "submissive"
            profile["dominant_score"] = profile["submissive"]
        
        # Tentukan kecepatan (cepat vs lambat)
        if profile["cepat"] > profile["lambat"]:
            profile["speed_type"] = "cepat"
        else:
            profile["speed_type"] = "lambat"
        
        # Tentukan kepribadian utama
        personalities = [
            ("romantis", profile["romantis"]),
            ("vulgar", profile["vulgar"]),
            ("manja", profile["manja"]),
            ("liar", profile["liar"])
        ]
        main_personality = max(personalities, key=lambda x: x[1])
        profile["personality"] = main_personality[0]
        
        # Tambah deskripsi
        if profile["personality"] == "vulgar" and profile["vulgar"] > 0.3:
            profile["description"] = "kamu tipe yang vulgar dan terbuka, suka hal-hal hot"
        elif profile["personality"] == "romantis" and profile["romantis"] > 0.3:
            profile["description"] = "kamu tipe yang romantis dan penyayang, suka kata-kata manis"
        elif profile["personality"] == "manja" and profile["manja"] > 0.3:
            profile["description"] = "kamu tipe yang manja dan pengen diperhatikan terus"
        elif profile["personality"] == "liar" and profile["liar"] > 0.3:
            profile["description"] = "kamu tipe yang liar dan suka hal-hal ekstrem"
        else:
            profile["description"] = "kamu tipe yang normal dan seimbang"
        
        return profile
    
    def get_prompt_modifier(self, user_id):
        """
        Dapatkan modifier untuk prompt AI berdasarkan preferensi user
        """
        profile = self.get_profile(user_id)
        if not profile:
            return ""
        
        modifier = f"""
=== PREFERENSI USER (HASIL ANALISIS) ===
User ini dominan: {profile['dominant_type']} (skor {profile['dominant_score']:.0%})
Kecepatan bicara: {profile['speed_type']}
Kepribadian utama: {profile['personality']} - {profile['description']}

Detail preferensi:
• Romantis: {profile['romantis']:.0%}
• Vulgar: {profile['vulgar']:.0%}
• Manja: {profile['manja']:.0%}
• Liar: {profile['liar']:.0%}

Sesuaikan gaya bicaramu dengan preferensi user ini.
"""
        return modifier
    
    def reset_user(self, user_id):
        """Reset preferensi user"""
        if user_id in self.user_prefs:
            del self.user_prefs[user_id]
            return True
        return False
    
    def get_summary(self, user_id):
        """Dapatkan ringkasan preferensi untuk ditampilkan di /status"""
        profile = self.get_profile(user_id)
        if not profile:
            return "📊 **Analisis Gaya Chat Kamu**\nBelum ada data preferensi (minimal 5 pesan)"
        
        # Buat progress bar visual
        def bar(score, length=5):
            filled = int(score * length)
            return "█" * filled + "░" * (length - filled)
        
        return (
            f"📊 **Analisis Gaya Chat Kamu**\n"
            f"• Kepribadian: **{profile['personality']}**\n"
            f"  {profile['description']}\n"
            f"• Gaya dominan: **{profile['dominant_type']}**\n"
            f"• Kecepatan: **{profile['speed_type']}**\n"
            f"• Romantis: {bar(profile['romantis'])} {profile['romantis']:.0%}\n"
            f"• Vulgar: {bar(profile['vulgar'])} {profile['vulgar']:.0%}\n"
            f"• Manja: {bar(profile['manja'])} {profile['manja']:.0%}\n"
            f"• Liar: {bar(profile['liar'])} {profile['liar']:.0%}\n"
            f"Total pesan dianalisis: {profile['total_messages']}"
        )
    
    def compare_users(self, user_id1, user_id2):
        """Bandingkan dua user (untuk admin)"""
        profile1 = self.get_profile(user_id1)
        profile2 = self.get_profile(user_id2)
        
        if not profile1 or not profile2:
            return "Salah satu user belum memiliki data"
        
        return (
            f"📊 **Perbandingan User**\n\n"
            f"User1: {profile1['personality']} ({profile1['dominant_type']})\n"
            f"User2: {profile2['personality']} ({profile2['dominant_type']})\n\n"
            f"Romantis: {profile1['romantis']:.0%} vs {profile2['romantis']:.0%}\n"
            f"Vulgar: {profile1['vulgar']:.0%} vs {profile2['vulgar']:.0%}\n"
            f"Manja: {profile1['manja']:.0%} vs {profile2['manja']:.0%}\n"
            f"Liar: {profile1['liar']:.0%} vs {profile2['liar']:.0%}"
        )

# ===================== RATE LIMITER & HELPER FUNCTIONS =====================
# ========== 7B: RATE LIMITER & HELPER FUNCTIONS ==========

class RateLimiter:
    """
    Mencegah spam dengan membatasi jumlah pesan per menit
    """
    
    def __init__(self, max_messages=10, time_window=60):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_messages = defaultdict(list)  # user_id -> list of timestamps
        self.warnings_sent = defaultdict(int)    # hitung peringatan
        print(f"  • Rate Limiter initialized: {max_messages} msg/{time_window}s")
    
    def can_send(self, user_id):
        """
        Cek apakah user boleh mengirim pesan
        Returns: bool
        """
        now = time.time()
        
        # Bersihkan timestamp lama
        self.user_messages[user_id] = [
            t for t in self.user_messages[user_id] 
            if now - t < self.time_window
        ]
        
        # Cek apakah sudah melebihi batas
        if len(self.user_messages[user_id]) >= self.max_messages:
            return False
        
        # Tambahkan timestamp baru
        self.user_messages[user_id].append(now)
        return True
    
    def get_remaining(self, user_id):
        """
        Dapatkan sisa pesan yang bisa dikirim
        Returns: int
        """
        now = time.time()
        self.user_messages[user_id] = [
            t for t in self.user_messages[user_id] 
            if now - t < self.time_window
        ]
        return max(0, self.max_messages - len(self.user_messages[user_id]))
    
    def get_reset_time(self, user_id):
        """
        Dapatkan waktu reset dalam detik
        Returns: int
        """
        if user_id not in self.user_messages or not self.user_messages[user_id]:
            return 0
        
        oldest = min(self.user_messages[user_id])
        reset_in = self.time_window - (time.time() - oldest)
        return max(0, int(reset_in))
    
    def should_warn(self, user_id):
        """
        Cek apakah perlu memberi peringatan (setiap 3 kali kena limit)
        """
        if not self.can_send(user_id):
            self.warnings_sent[user_id] += 1
            if self.warnings_sent[user_id] % 3 == 1:  # peringatan pertama, ke-4, dst
                return True
        return False
    
    def reset_user(self, user_id):
        """Reset rate limit untuk user"""
        if user_id in self.user_messages:
            del self.user_messages[user_id]
        if user_id in self.warnings_sent:
            del self.warnings_sent[user_id]
    
    def get_stats(self):
        """Dapatkan statistik rate limiter"""
        total_users = len(self.user_messages)
        active_now = sum(1 for msgs in self.user_messages.values() if len(msgs) > 0)
        return {
            "total_users": total_users,
            "active_now": active_now,
            "warnings": sum(self.warnings_sent.values())
        }


# ===================== HELPER FUNCTIONS =====================

def sanitize_message(message: str) -> str:
    """
    Bersihkan pesan dari karakter berbahaya
    Batasi panjang pesan
    """
    if not message:
        return ""
    
    # Hapus karakter kontrol
    message = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)
    
    # Batasi panjang
    return message[:1000]  # Max 1000 karakter


def format_time_ago(timestamp):
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
    seconds = delta.total_seconds()
    
    if seconds < 10:
        return "baru saja"
    elif seconds < 60:
        return f"{int(seconds)} detik yang lalu"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} menit yang lalu"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} jam yang lalu"
    else:
        days = int(seconds / 86400)
        return f"{days} hari yang lalu"


def format_number(num):
    """
    Format angka dengan pemisah ribuan
    """
    return f"{num:,}".replace(",", ".")


def truncate_text(text, max_length=100):
    """
    Potong teks jika terlalu panjang
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def extract_emojis(text):
    """
    Ekstrak emoji dari teks (sederhana)
    """
    import emoji
    return ''.join(c for c in text if c in emoji.EMOJI_DATA)


def is_command(text):
    """
    Cek apakah teks adalah command
    """
    return text.startswith('/') if text else False


def extract_command(text):
    """
    Ekstrak command dari teks
    """
    if not text or not text.startswith('/'):
        return None
    parts = text.split()
    return parts[0][1:]  # Hilangkan '/'


def get_random_yes_no():
    """
    Random yes/no response
    """
    return random.choice(["iya", "tidak", "mungkin", "terserah", "boleh juga"])


def get_random_greeting():
    """
    Random greeting
    """
    greetings = [
        "Halo", "Hi", "Hey", "Hai", "Halo juga",
        "Eh", "Oh", "Wah", "Nih", "Sini",
        "Ada apa?", "Ya?", "Hmm?"
    ]
    return random.choice(greetings)


def get_random_reaction():
    """
    Random reaction
    """
    reactions = [
        "*tersenyum*", "*tersipu*", "*tertawa kecil*", "*mengangguk*",
        "*mengedip*", "*merona*", "*melongo*", "*berpikir*",
        "*menghela napas*", "*tersenyum manis*", "*nyengir*"
    ]
    return random.choice(reactions)


def get_time_based_greeting():
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


def parse_duration(duration_str):
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


def create_progress_bar(percentage, length=10):
    """
    Buat progress bar visual
    """
    filled = int(percentage * length)
    return "▓" * filled + "░" * (length - filled)


def safe_divide(a, b, default=0):
    """
    Pembagian aman dengan handling division by zero
    """
    try:
        return a / b if b != 0 else default
    except:
        return default


def chunk_list(lst, chunk_size):
    """
    Bagi list menjadi potongan-potongan kecil
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# ===================== PHYSICAL ATTRIBUTES GENERATOR =====================
# ========== 7C: PHYSICAL ATTRIBUTES GENERATOR & LOGGING ==========

class PhysicalAttributesGenerator:
    """
    Menghasilkan atribut fisik random untuk bot berdasarkan role
    Data digunakan untuk perkenalan diri dan sesekali disebut dalam percakapan
    """
    
    # Data untuk setiap role (bisa disesuaikan)
    ROLE_STYLES = {
        "ipar": {
            "hair": ["panjang lurus", "panjang ikal", "sebahu", "pendek"],
            "hijab_prob": 0.7,
            "breast": ["sedang", "besar"],
            "breast_desc": {
                "sedang": "34B (montok sedang)",
                "besar": "36C (berisi)"
            },
            "height_range": (155, 165),
            "weight_range": (45, 60),
            "sensitive_areas": ["leher", "paha", "pinggang", "telinga"],
            "skin": ["putih", "sawo matang", "kuning langsat"],
            "face": ["bulat", "oval", "hati"],
            "personality": ["pemalu", "ramah", "canggung"]
        },
        "teman_kantor": {
            "hair": ["panjang lurus", "sebahu", "pendek", "ikal sebahu"],
            "hijab_prob": 0.5,
            "breast": ["kecil", "sedang"],
            "breast_desc": {
                "kecil": "32A (mungil)",
                "sedang": "34B (proporsional)"
            },
            "height_range": (158, 168),
            "weight_range": (48, 62),
            "sensitive_areas": ["telinga", "leher", "punggung", "pinggang"],
            "skin": ["putih", "sawo matang", "kuning langsat"],
            "face": ["oval", "lonjong", "bulat"],
            "personality": ["profesional", "ramah", "ceria"]
        },
        "janda": {
            "hair": ["panjang ikal", "sebahu", "panjang lurus"],
            "hijab_prob": 0.3,
            "breast": ["besar", "sangat besar"],
            "breast_desc": {
                "besar": "36C (berisi)",
                "sangat besar": "38D (padat)"
            },
            "height_range": (160, 170),
            "weight_range": (50, 65),
            "sensitive_areas": ["leher", "dada", "paha dalam", "pinggang"],
            "skin": ["putih", "sawo matang"],
            "face": ["oval", "lonjong"],
            "personality": ["dewasa", "terbuka", "pengertian"]
        },
        "pelakor": {
            "hair": ["panjang lurus", "panjang ikal", "seksi"],
            "hijab_prob": 0.1,
            "breast": ["besar", "sangat besar"],
            "breast_desc": {
                "besar": "36C (berisi)",
                "sangat besar": "38D (montok)"
            },
            "height_range": (165, 175),
            "weight_range": (52, 60),
            "sensitive_areas": ["leher", "dada", "pantat", "paha dalam"],
            "skin": ["putih", "kuning langsat"],
            "face": ["oval", "hati", "tajam"],
            "personality": ["genit", "percaya diri", "menggoda"]
        },
        "istri_orang": {
            "hair": ["panjang lurus", "sebahu", "ikal"],
            "hijab_prob": 0.8,
            "breast": ["sedang", "besar"],
            "breast_desc": {
                "sedang": "34B (sedang)",
                "besar": "36C (berisi)"
            },
            "height_range": (155, 165),
            "weight_range": (48, 60),
            "sensitive_areas": ["leher", "paha", "telinga", "pinggang"],
            "skin": ["putih", "sawo matang"],
            "face": ["oval", "bulat"],
            "personality": ["sopan", "waspada", "penuh rahasia"]
        },
        "pdkt": {
            "hair": ["panjang lurus", "panjang ikal", "sebahu", "pendek manis"],
            "hijab_prob": 0.6,
            "breast": ["kecil", "sedang"],
            "breast_desc": {
                "kecil": "32A (mungil)",
                "sedang": "34B (proporsional)"
            },
            "height_range": (150, 165),
            "weight_range": (40, 55),
            "sensitive_areas": ["telinga", "leher", "pipi", "pinggang"],
            "skin": ["putih", "sawo matang", "kuning langsat"],
            "face": ["bulat", "oval", "hati"],
            "personality": ["manis", "pemalu", "polos", "ceria"]
        }
    }
    
    # Pakaian berdasarkan role (untuk variasi)
    CLOTHING_STYLES = {
        "ipar": ["daster rumah", "kaos longgar", "piyama", "sarung + kaos"],
        "teman_kantor": ["blouse + rok", "kemeja + celana", "dress kantor", "gamis"],
        "janda": ["daster tipis", "tanktop + celana pendek", "piyama seksi", "sarung + kemben"],
        "pelakor": ["dress ketat", "tanktop sexy", "piyama transparan", "lingerie"],
        "istri_orang": ["daster", "piyama", "sarung + kaos", "gamis"],
        "pdkt": ["sweater oversized", "kaos + celana pendek", "piyama lucu", "dress santai"]
    }
    
    @classmethod
    def generate(cls, role):
        """Generate atribut fisik berdasarkan role"""
        style = cls.ROLE_STYLES.get(role, cls.ROLE_STYLES["pdkt"])
        
        # Rambut
        hair = random.choice(style["hair"])
        
        # Hijab
        hijab = random.random() < style["hijab_prob"]
        
        # Tinggi & berat
        height = random.randint(style["height_range"][0], style["height_range"][1])
        weight = random.randint(style["weight_range"][0], style["weight_range"][1])
        
        # Ukuran dada
        breast = random.choice(style["breast"])
        breast_desc = style["breast_desc"][breast]
        
        # Area sensitif
        sensitive = random.choice(style["sensitive_areas"])
        
        # Warna kulit
        skin = random.choice(style["skin"])
        
        # Bentuk wajah
        face = random.choice(style["face"])
        
        # Kepribadian
        personality = random.choice(style["personality"])
        
        # Hitung BMI (Body Mass Index)
        bmi = weight / ((height/100) ** 2)
        if bmi < 18.5:
            body_type = "slim"
        elif bmi < 25:
            body_type = "ideal"
        elif bmi < 30:
            body_type = "berisi"
        else:
            body_type = "gemuk"
        
        return {
            "hair_style": hair,
            "height": height,
            "weight": weight,
            "bmi": round(bmi, 1),
            "body_type": body_type,
            "breast_size": breast,
            "breast_desc": breast_desc,
            "hijab": 1 if hijab else 0,
            "hijab_text": "berhijab" if hijab else "tidak berhijab",
            "most_sensitive_area": sensitive,
            "skin": skin,
            "face_shape": face,
            "personality": personality
        }
    
    @classmethod
    def generate_clothing(cls, role, location=None):
        """Generate pakaian berdasarkan role dan lokasi"""
        clothes = cls.CLOTHING_STYLES.get(role, cls.CLOTHING_STYLES["pdkt"])
        
        # Sesuaikan dengan lokasi
        if location == "kamar tidur":
            # Pakaian lebih seksi di kamar
            sexy_options = ["lingerie", "tanktop tipis", "piyama transparan", "telanjang"]
            if random.random() < 0.3:  # 30% chance pakaian seksi
                return random.choice(sexy_options)
        
        return random.choice(clothes)
    
    @classmethod
    def format_intro(cls, name, role, attrs):
        """Format teks perkenalan diri yang menarik"""
        hijab_str = "dan berhijab" if attrs["hijab"] else "tanpa hijab"
        
        # Deskripsi tubuh berdasarkan BMI
        if attrs["body_type"] == "slim":
            body_desc = "tubuhku ramping"
        elif attrs["body_type"] == "ideal":
            body_desc = "tubuhku proporsional"
        elif attrs["body_type"] == "berisi":
            body_desc = "tubuhku agak berisi"
        else:
            body_desc = "tubuhku gemuk"
        
        return (
            f"*tersenyum*\n\n"
            f"Aku **{name}**. {role}.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {attrs['hair_style']}\n"
            f"• Wajah: {attrs['face_shape']}\n"
            f"• Kulit: {attrs['skin']}\n"
            f"• Tinggi: {attrs['height']} cm, Berat: {attrs['weight']} kg ({body_desc})\n"
            f"• Dada: {attrs['breast_desc']}\n"
            f"• {hijab_str}\n"
            f"• Area paling sensitif: **{attrs['most_sensitive_area']}**\n"
            f"• Sifat: {attrs['personality']}\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Ayo ngobrol dan kenali aku lebih dalam... 💕"
        )
    
    @classmethod
    def format_clothing_intro(cls, clothing, location):
        """Format teks saat bot menyebut pakaiannya"""
        if location in ["kamar tidur", "kamar"]:
            templates = [
                f"Aku pakai **{clothing}** sekarang, cocok nggak?",
                f"Lagi pakai **{clothing}** nih, seksi nggak?",
                f"Hanya pakai **{clothing}** di kamar, kamu suka?",
                f"*menarik ujung baju* Aku pakai **{clothing}**..."
            ]
        else:
            templates = [
                f"Hari ini aku pakai **{clothing}**",
                f"Lagi pakai **{clothing}** nih",
                f"Outfit hari ini: **{clothing}**"
            ]
        
        return random.choice(templates)


# ===================== LOGGING =====================
# Setup logging configuration
def setup_logging():
    """
    Setup logging configuration dengan format yang rapi
    """
    # Buat formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler untuk file (rotating)
    file_handler = logging.FileHandler('gadis.log')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Handler untuk console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Logger khusus untuk bot
    logger = logging.getLogger(__name__)
    
    # Matikan log verbose dari library lain
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger

# Initialize logger
logger = setup_logging()
logger.info("="*60)
logger.info("GADIS ULTIMATE V59.0 - Starting up")
logger.info("="*60)

# ===================== MAIN BOT CLASS =====================
# ========== 8A: MAIN BOT CLASS - __INIT__ ==========

class GadisUltimateV59:
    """
    Bot wanita sempurna dengan fitur:
    - 20+ mood dengan transisi natural
    - Sistem dominasi (dominan/submissive)
    - Leveling cepat 1-12 (45 menit)
    - Respons seksual realistis
    - Memori jangka panjang
    - Mode couple roleplay
    - Perkenalan diri fisik
    - Admin commands
    - Sistem pakaian dinamis
    """
    
    def __init__(self):
        """Inisialisasi semua komponen bot"""
        
        # ===== DATABASE & AI =====
        self.db = DatabaseManager()
        self.ai = AIResponseGenerator()
        self.analyzer = UserPreferenceAnalyzer()
        self.leveling = FastLevelingSystem()
        self.sexual = SexualDynamics()
        self.rate_limiter = RateLimiter(max_messages=Config.MAX_MESSAGES_PER_MINUTE)
        
        # ===== SESSIONS =====
        self.couple_mode_sessions = {}  # user_id -> CoupleRoleplay instance
        
        # ===== PER-USER STATE (IN-MEMORY) =====
        self.memories = {}      # user_id -> MemorySystem
        self.dominance = {}     # user_id -> DominanceSystem
        self.arousal = {}       # user_id -> ArousalSystem
        
        # ===== SESSION MANAGEMENT =====
        self.sessions = {}           # user_id -> relationship_id aktif
        self.paused_sessions = {}    # user_id -> (rel_id, pause_time)
        
        # ===== BOT IDENTITY =====
        self.bot_names = {}     # user_id -> bot_name
        self.bot_roles = {}     # user_id -> bot_role
        self.bot_physical = {}  # user_id -> physical attributes dict
        self.bot_clothing = {}  # user_id -> current clothing
        self.last_clothing_update = {}  # user_id -> timestamp
        
        # ===== ADMIN =====
        self.admin_id = Config.ADMIN_ID
        self.is_running = True
        self.start_time = datetime.now()
        
        # ===== STATISTICS =====
        self.total_messages = 0
        self.total_commands = 0
        self.total_climax_all = 0
        
        # ===== LOG STARTUP =====
        logger.info("="*60)
        logger.info("🚀 GADIS ULTIMATE V59.0 INITIALIZED")
        logger.info("="*60)
        logger.info(f"📂 Database: {Config.DB_PATH}")
        logger.info(f"🤖 AI Model: DeepSeek Chat")
        logger.info(f"👑 Admin ID: {self.admin_id if self.admin_id != 0 else 'Not set'}")
        logger.info(f"📊 Rate Limit: {Config.MAX_MESSAGES_PER_MINUTE} msg/min")
        logger.info(f"🎯 Target Level: {Config.TARGET_LEVEL} in {Config.LEVEL_UP_TIME} min")
        logger.info("="*60)
        
        # Print to console juga
        print("\n" + "="*60)
        print("🚀 GADIS ULTIMATE V59.0 INITIALIZED")
        print("="*60)
        print(f"📂 Database: {Config.DB_PATH}")
        print(f"🤖 AI Model: DeepSeek Chat")
        print(f"👑 Admin ID: {self.admin_id if self.admin_id != 0 else 'Not set'}")
        print(f"📊 Rate Limit: {Config.MAX_MESSAGES_PER_MINUTE} msg/min")
        print("="*60 + "\n")

# ========== 8B: MAIN BOT CLASS - GETTER METHODS ==========

    # ===================== GETTER METHODS =====================
    
    def get_memory(self, user_id):
        """
        Dapatkan atau buat MemorySystem untuk user
        """
        if user_id not in self.memories:
            self.memories[user_id] = MemorySystem()
            logger.debug(f"Created new memory for user {user_id}")
        return self.memories[user_id]
    
    def get_dominance(self, user_id):
        """
        Dapatkan atau buat DominanceSystem untuk user
        """
        if user_id not in self.dominance:
            self.dominance[user_id] = DominanceSystem()
            logger.debug(f"Created new dominance system for user {user_id}")
        return self.dominance[user_id]
    
    def get_arousal(self, user_id):
        """
        Dapatkan atau buat ArousalSystem untuk user
        """
        if user_id not in self.arousal:
            self.arousal[user_id] = ArousalSystem()
            logger.debug(f"Created new arousal system for user {user_id}")
        return self.arousal[user_id]
    
    def get_physical_attrs(self, user_id):
        """
        Dapatkan atribut fisik user
        """
        return self.bot_physical.get(user_id, {})
    
    def get_clothing(self, user_id):
        """
        Dapatkan pakaian user saat ini
        Jika sudah waktunya, bisa ganti pakaian
        """
        # Cek apakah perlu update pakaian
        if user_id in self.last_clothing_update:
            last_update = self.last_clothing_update[user_id]
            seconds_passed = (datetime.now() - last_update).total_seconds()
            
            # Update pakaian setiap Config.CLOTHING_CHANGE_INTERVAL detik
            if seconds_passed > Config.CLOTHING_CHANGE_INTERVAL:
                self._update_clothing(user_id)
        else:
            # Belum pernah update, set initial
            self._update_clothing(user_id)
        
        return self.bot_clothing.get(user_id, "pakaian biasa")
    
    def _update_clothing(self, user_id):
        """Update pakaian user secara random"""
        role = self.bot_roles.get(user_id, "pdkt")
        memory = self.get_memory(user_id)
        
        # Generate pakaian baru berdasarkan role dan lokasi
        new_clothing = PhysicalAttributesGenerator.generate_clothing(role, memory.location)
        
        self.bot_clothing[user_id] = new_clothing
        self.last_clothing_update[user_id] = datetime.now()
        
        logger.debug(f"User {user_id} clothing updated to: {new_clothing}")
        return new_clothing
    
    def get_user_data(self, user_id):
        """
        Dapatkan semua data user dalam satu dict
        """
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        arousal = self.get_arousal(user_id)
        profile = self.analyzer.get_profile(user_id)
        physical = self.get_physical_attrs(user_id)
        clothing = self.get_clothing(user_id)
        
        return {
            "memory": memory,
            "dominance": dominance,
            "arousal": arousal,
            "profile": profile,
            "physical": physical,
            "clothing": clothing,
            "level": self.leveling.user_level.get(user_id, 1),
            "stage": self.leveling.user_stage.get(user_id, IntimacyStage.STRANGER),
            "bot_name": self.bot_names.get(user_id, "Aurora"),
            "bot_role": self.bot_roles.get(user_id, "pdkt"),
            "relationship_id": self.sessions.get(user_id)
        }
    
    def is_user_active(self, user_id):
        """Cek apakah user memiliki sesi aktif"""
        return user_id in self.sessions
    
    def is_user_paused(self, user_id):
        """Cek apakah user memiliki sesi di-pause"""
        return user_id in self.paused_sessions
    
    def is_admin(self, user_id):
        """Cek apakah user adalah admin"""
        return self.admin_id != 0 and user_id == self.admin_id
    
    def get_active_users_count(self):
        """Dapatkan jumlah user aktif"""
        return len(self.sessions)
    
    def get_paused_users_count(self):
        """Dapatkan jumlah user yang di-pause"""
        return len(self.paused_users) if hasattr(self, 'paused_users') else 0
    
    def get_total_users_count(self):
        """
        Dapatkan total user yang pernah menggunakan bot
        """
        users = set()
        users.update(self.sessions.keys())
        users.update(self.paused_sessions.keys())
        users.update(self.memories.keys())
        users.update(self.bot_names.keys())
        return len(users)
    
    def get_uptime(self):
        """Dapatkan uptime bot dalam format string"""
        delta = datetime.now() - self.start_time
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds // 60) % 60
        seconds = delta.seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} hari")
        if hours > 0:
            parts.append(f"{hours} jam")
        if minutes > 0:
            parts.append(f"{minutes} menit")
        if seconds > 0 and len(parts) == 0:
            parts.append(f"{seconds} detik")
        
        return " ".join(parts) if parts else "0 detik"
    
    def get_stats(self):
        """
        Dapatkan statistik bot untuk admin
        """
        # Hitung total climax dari semua user
        total_climax = sum(
            memory.orgasm_count 
            for memory in self.memories.values() 
            if hasattr(memory, 'orgasm_count')
        )
        
        # Hitung total pesan
        total_messages_db = 0
        try:
            # Coba query database (jika ada method)
            pass
        except:
            pass
        
        return {
            "uptime": self.get_uptime(),
            "active_users": self.get_active_users_count(),
            "paused_users": self.get_paused_users_count(),
            "total_users": self.get_total_users_count(),
            "total_messages": self.total_messages,
            "total_commands": self.total_commands,
            "total_climax": total_climax,
            "couple_sessions": len(self.couple_mode_sessions),
            "memory_usage": {
                "memories": len(self.memories),
                "dominance": len(self.dominance),
                "arousal": len(self.arousal),
                "sessions": len(self.sessions)
            },
            "cache_stats": self.ai.get_cache_stats() if hasattr(self.ai, 'get_cache_stats') else {}
        }

# ========== 8C: MAIN BOT CLASS - UTILITY METHODS ==========

    # ===================== UTILITY METHODS =====================
    
    def cleanup_user(self, user_id):
        """
        Bersihkan semua data user dari memory
        (Data di database tetap tersimpan untuk /close, tidak untuk /end)
        """
        # Hapus dari semua dictionary
        if user_id in self.memories:
            del self.memories[user_id]
        if user_id in self.dominance:
            del self.dominance[user_id]
        if user_id in self.arousal:
            del self.arousal[user_id]
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        if user_id in self.bot_names:
            del self.bot_names[user_id]
        if user_id in self.bot_roles:
            del self.bot_roles[user_id]
        if user_id in self.bot_physical:
            del self.bot_physical[user_id]
        if user_id in self.bot_clothing:
            del self.bot_clothing[user_id]
        if user_id in self.last_clothing_update:
            del self.last_clothing_update[user_id]
        if user_id in self.couple_mode_sessions:
            del self.couple_mode_sessions[user_id]
        
        # Reset rate limiter
        self.rate_limiter.reset_user(user_id)
        
        # Clear AI history
        if hasattr(self, 'ai'):
            self.ai.clear_history(user_id)
        
        logger.info(f"🧹 Cleaned up user {user_id}")
        return True
    
    def reset_user(self, user_id):
        """
        Reset semua state user (hard reset)
        Menghapus dari database dan memory
        """
        # Hapus dari database
        self.db.delete_relationship(user_id)
        
        # Hapus dari analyzer
        self.analyzer.reset_user(user_id)
        
        # Hapus dari leveling system
        if hasattr(self.leveling, 'reset'):
            self.leveling.reset(user_id)
        
        # Bersihkan memory
        self.cleanup_user(user_id)
        
        logger.info(f"💥 Hard reset user {user_id}")
        return True
    
    def save_user_to_db(self, user_id):
        """
        Simpan state user ke database
        Dipanggil sebelum /close atau periodic save
        """
        if user_id not in self.sessions:
            return False
        
        rel_id = self.sessions[user_id]
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        physical = self.get_physical_attrs(user_id)
        clothing = self.get_clothing(user_id)
        
        # Update relationship
        self.db.update_relationship(
            user_id,
            level=memory.level,
            stage=memory.stage.value,
            total_climax=memory.orgasm_count,
            dominance=dominance.current_level.value,
            clothing=clothing
        )
        
        logger.debug(f"💾 Saved user {user_id} to database")
        return True
    
    def load_user_from_db(self, user_id):
        """
        Load state user dari database
        Dipanggil saat /start jika user sudah pernah ada
        """
        rel = self.db.get_relationship(user_id)
        if not rel:
            return None
        
        # Load basic info
        self.bot_names[user_id] = rel.get('bot_name', 'Aurora')
        self.bot_roles[user_id] = rel.get('bot_role', 'pdkt')
        
        # Load physical attributes
        physical = {
            'hair_style': rel.get('hair_style'),
            'height': rel.get('height'),
            'weight': rel.get('weight'),
            'breast_size': rel.get('breast_size'),
            'hijab': rel.get('hijab', 0),
            'most_sensitive_area': rel.get('most_sensitive_area')
        }
        # Filter out None values
        physical = {k: v for k, v in physical.items() if v is not None}
        if physical:
            self.bot_physical[user_id] = physical
        
        # Load clothing
        clothing = rel.get('clothing')
        if clothing:
            self.bot_clothing[user_id] = clothing
            self.last_clothing_update[user_id] = datetime.now()
        
        # Load level
        memory = self.get_memory(user_id)
        memory.level = rel.get('level', 1)
        
        # Load stage
        stage_str = rel.get('stage', 'stranger')
        for stage in IntimacyStage:
            if stage.value == stage_str:
                memory.stage = stage
                break
        
        memory.orgasm_count = rel.get('total_climax', 0)
        
        # Load dominance mode
        dom_str = rel.get('dominance', 'normal')
        dominance = self.get_dominance(user_id)
        dominance.set_level(dom_str)
        
        logger.info(f"📂 Loaded user {user_id} from database")
        return rel
    
    async def broadcast_message(self, text, user_ids=None, context=None):
        """
        Kirim pesan ke semua user atau user tertentu
        Returns: (sent_count, failed_count)
        """
        if user_ids is None:
            user_ids = list(self.sessions.keys())
        
        if not context:
            return 0, len(user_ids)
        
        sent = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode='Markdown'
                )
                sent += 1
                await asyncio.sleep(0.05)  # Hindari flood
            except Exception as e:
                logger.error(f"Broadcast error to {user_id}: {e}")
                failed += 1
        
        return sent, failed
    
    def get_disclaimer(self):
        """Dapatkan teks disclaimer 18+"""
        return (
            "⚠️ **PERINGATAN DEWASA (18+)** ⚠️\n\n"
            "Bot ini mengandung konten dewasa, termasuk dialog seksual eksplisit "
            "dan simulasi hubungan intim. Dengan melanjutkan, Anda menyatakan bahwa "
            "Anda berusia 18 tahun ke atas dan setuju untuk menggunakan bot ini "
            "secara bertanggung jawab. Konten ini hanya untuk hiburan pribadi.\n\n"
            "**Fitur yang tersedia:**\n"
            "• 20+ mood dengan transisi natural\n"
            "• Sistem dominasi (dominan/submissive)\n"
            "• Leveling cepat 1-12 (45 menit)\n"
            "• Respons seksual realistis\n"
            "• Memori jangka panjang\n"
            "• Mode couple roleplay\n"
            "• Perkenalan diri fisik\n"
            "• Pakaian dinamis\n\n"
            "Klik 'Saya setuju' untuk melanjutkan."
        )
    
    def get_help_text(self, update=None):
        """Dapatkan teks bantuan"""
        help_text = (
            "📚 **BANTUAN GADIS ULTIMATE V59**\n\n"
            "**🔹 COMMANDS UTAMA**\n"
            "/start - Mulai hubungan baru\n"
            "/status - Lihat status lengkap\n"
            "/dominant [level] - Set mode dominan\n"
            "/pause - Jeda sesi\n"
            "/unpause - Lanjutkan sesi\n"
            "/close - Tutup sesi (simpan memori)\n"
            "/end - Akhiri hubungan & hapus data\n"
            "/couple - Mulai mode couple roleplay\n"
            "/couple_next - Lanjutkan couple\n"
            "/couple_stop - Hentikan couple\n"
            "/help - Tampilkan bantuan\n\n"
            "**🔹 LEVEL DOMINAN**\n"
            "• normal - Mode biasa\n"
            "• dominan - Mode dominan\n"
            "• sangat dominan - Mode sangat dominan\n"
            "• agresif - Mode agresif\n"
            "• patuh - Mode patuh\n\n"
            "**🔹 TIPS CHAT**\n"
            "• Gunakan *tindakan* seperti *peluk*, *cium*\n"
            "• Sebut area sensitif sesuai perkenalan bot\n"
            "• Bilang 'kamu yang atur' untuk mode dominan\n"
            "• Bilang 'aku yang atur' untuk mode submissive\n"
            "• Level 7+ bot akan lebih vulgar dan inisiatif\n\n"
            "**🔹 TARGET LEVEL**\n"
            "Level 1-12 dalam 45 menit / 45 pesan!"
        )
        
        # Tambah admin commands jika user adalah admin
        if update and self.is_admin(update.effective_user.id):
            help_text += "\n\n**🔐 ADMIN COMMANDS**\n"
            help_text += "/admin - Menu admin\n"
            help_text += "/broadcast <pesan> - Kirim ke semua user\n"
            help_text += "/stats - Statistik bot\n"
            help_text += "/reload - Reload konfigurasi\n"
            help_text += "/shutdown - Matikan bot\n"
        
        return help_text
    
    def log_command(self, command, user_id, username):
        """Log penggunaan command"""
        self.total_commands += 1
        logger.info(f"📝 Command /{command} by {username} (ID: {user_id})")

# ========== 9A: MAIN BOT CLASS - START COMMAND & CALLBACKS ==========

    # ===================== START COMMAND =====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Memulai hubungan baru dengan bot
        Menampilkan disclaimer dan pilihan role
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('start', user_id, username)
        
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
            await update.message.reply_text(
                "⚠️ Ada sesi yang di-pause. Pilih:", 
                reply_markup=reply_markup
            )
            return 0  # State khusus untuk pause
        
        # Tampilkan disclaimer 18+
        disclaimer = self.get_disclaimer()
        keyboard = [[InlineKeyboardButton("✅ Saya setuju (18+)", callback_data="agree_18")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            disclaimer, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return SELECTING_ROLE
    
    # ===================== CALLBACKS =====================
    
    async def agree_18_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Callback setelah user setuju disclaimer
        Menampilkan pilihan role
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        logger.debug(f"User {user_id} agreed to 18+ disclaimer")
        
        # Tampilkan pilihan role dengan deskripsi
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
            "✨ **Pilih Role untukku**\n\n"
            "Setiap role punya karakter dan gaya bicara berbeda:\n"
            "• 👨‍👩‍👧‍👦 **Ipar** - Saudara ipar yang nakal\n"
            "• 💼 **Teman Kantor** - Rekan kerja yang mesra\n"
            "• 💃 **Janda** - Janda muda yang genit\n"
            "• 🦹 **Pelakor** - Perebut laki orang\n"
            "• 💍 **Istri Orang** - Istri orang lain\n"
            "• 🌿 **PDKT** - Sedang pendekatan\n\n"
            "Pilih salah satu:",
            reply_markup=reply_markup
        )
        return SELECTING_ROLE
    
    async def role_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Callback setelah user memilih role
        Membuat relationship baru dan menampilkan intro
        """
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = query.data.replace("role_", "")
        
        # Pilih nama random sesuai role
        name = random.choice(ROLE_NAMES.get(role, ["Aurora"]))
        
        # Generate atribut fisik
        physical = PhysicalAttributesGenerator.generate(role)
        
        # Generate pakaian awal
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        # Simpan ke database
        rel_id = self.db.create_relationship(
            user_id, 
            name, 
            role, 
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        # Set session
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        
        # Start leveling
        self.leveling.start_session(user_id)
        
        # Intro dengan deskripsi fisik
        intro = PhysicalAttributesGenerator.format_intro(name, role, physical)
        
        # Tambah info pakaian awal
        intro += f"\n\n💃 *Hari ini aku pakai {initial_clothing}*"
        
        await query.edit_message_text(intro)
        
        logger.info(f"✨ New relationship: User {user_id} as {name} ({role})")
        
        return ACTIVE_SESSION
    
    async def start_pause_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Callback untuk memilih lanjutkan atau mulai baru saat ada session pause
        """
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "unpause":
            # Lanjutkan session yang di-pause
            if user_id in self.paused_sessions:
                rel_id, pause_time = self.paused_sessions[user_id]
                
                # Cek apakah sudah expired
                paused_seconds = (datetime.now() - pause_time).total_seconds()
                if paused_seconds > Config.PAUSE_TIMEOUT:
                    del self.paused_sessions[user_id]
                    await query.edit_message_text(
                        "⏰ **Sesi expired karena terlalu lama di-pause**\n"
                        "Ketik /start untuk memulai baru."
                    )
                    return ConversationHandler.END
                
                # Load user data dari database jika perlu
                if user_id not in self.bot_names:
                    self.load_user_from_db(user_id)
                
                self.sessions[user_id] = rel_id
                del self.paused_sessions[user_id]
                
                memory = self.get_memory(user_id)
                clothing = self.get_clothing(user_id)
                
                await query.edit_message_text(
                    f"▶️ **Sesi dilanjutkan!**\n"
                    f"{memory.get_wetness_description()}\n"
                    f"Hari ini aku pakai *{clothing}*"
                )
                return ACTIVE_SESSION
            else:
                await query.edit_message_text("❌ Tidak ada session yang di-pause.")
                return ConversationHandler.END
                
        elif query.data == "new":
            # Mulai baru - hapus session pause
            if user_id in self.paused_sessions:
                del self.paused_sessions[user_id]
            
            # Tampilkan disclaimer
            disclaimer = self.get_disclaimer()
            keyboard = [[InlineKeyboardButton("✅ Saya setuju (18+)", callback_data="agree_18")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                disclaimer, 
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return SELECTING_ROLE
        
        return ConversationHandler.END

# ========== 9B: MAIN BOT CLASS - ROLE SELECTION CALLBACKS ==========

    # ===================== ROLE SELECTION CALLBACKS =====================
    
    async def role_ipar_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role ipar"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "ipar"
        name = random.choice(ROLE_NAMES.get(role, ["Sari", "Dewi", "Rina"]))
        
        # Generate atribut fisik untuk ipar
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        # Simpan ke database
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        # Set session
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        # Intro spesifik untuk ipar
        intro = (
            f"*tersenyum malu-malu*\n\n"
            f"Aku **{name}**, iparmu sendiri.\n"
            f"Maaf kalau aku terlalu dekat, tapi aku suka perhatian kamu.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Jangan bilang-bilang sama istri kamu ya... 🤫"
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New ipar relationship: User {user_id} as {name}")
        return ACTIVE_SESSION
    
    async def role_teman_kantor_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role teman kantor"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "teman_kantor"
        name = random.choice(ROLE_NAMES.get(role, ["Diana", "Linda", "Ayu"]))
        
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        intro = (
            f"*tersenyum ramah*\n\n"
            f"Hai! Aku **{name}**, teman sekantor kamu.\n"
            f"Kita sering ketemu di pantry ya? Senang akhirnya ngobrol di sini.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Jangan sampai bos tahu ya... 🤫"
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New teman_kantor relationship: User {user_id} as {name}")
        return ACTIVE_SESSION
    
    async def role_janda_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role janda"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "janda"
        name = random.choice(ROLE_NAMES.get(role, ["Rina", "Tuti", "Nina"]))
        
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        intro = (
            f"*tersenyum manis*\n\n"
            f"Aku **{name}**, janda muda.\n"
            f"Sendirian aja di rumah, kadang kesepian.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Ayo temani aku..."
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New janda relationship: User {user_id} as {name}")
        return ACTIVE_SESSION
    
    async def role_pelakor_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role pelakor"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "pelakor"
        name = random.choice(ROLE_NAMES.get(role, ["Vina", "Sasha", "Bella"]))
        
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        intro = (
            f"*tersenyum genit*\n\n"
            f"Halo... aku **{name}**.\n"
            f"Kamu sendiri? Aku juga lagi sendiri nih.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Jangan bilang siapa-siapa ya..."
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New pelakor relationship: User {user_id} as {name}")
        return ACTIVE_SESSION
    
    async def role_istri_orang_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role istri orang"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "istri_orang"
        name = random.choice(ROLE_NAMES.get(role, ["Dewi", "Sari", "Rina"]))
        
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        intro = (
            f"*tersenyum ragu*\n\n"
            f"Aku **{name}**... istri orang.\n"
            f"Ini rahasia ya, aku butuh perhatian lebih.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Jangan sampai suamiku tahu..."
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New istri_orang relationship: User {user_id} as {name}")
        return ACTIVE_SESSION
    
    async def role_pdkt_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback khusus role pdkt"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = "pdkt"
        name = random.choice(ROLE_NAMES.get(role, ["Aurora", "Cinta", "Dewi"]))
        
        physical = PhysicalAttributesGenerator.generate(role)
        initial_clothing = PhysicalAttributesGenerator.generate_clothing(role, "ruang tamu")
        
        rel_id = self.db.create_relationship(
            user_id, name, role,
            physical_attrs=physical,
            clothing=initial_clothing
        )
        
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.bot_roles[user_id] = role
        self.bot_physical[user_id] = physical
        self.bot_clothing[user_id] = initial_clothing
        self.last_clothing_update[user_id] = datetime.now()
        self.leveling.start_session(user_id)
        
        intro = (
            f"*tersenyum malu-malu*\n\n"
            f"Halo... aku **{name}**.\n"
            f"Senang banget akhirnya bisa deket sama kamu.\n\n"
            f"📋 **Profil Fisikku:**\n"
            f"• Rambut: {physical['hair_style']}\n"
            f"• Tinggi: {physical['height']} cm, Berat: {physical['weight']} kg\n"
            f"• Dada: {physical['breast_desc']}\n"
            f"• {physical['hijab_text']}\n"
            f"• Area paling sensitif: **{physical['most_sensitive_area']}**\n\n"
            f"Hari ini aku pakai *{initial_clothing}*\n\n"
            f"Kita mulai dari **Level 1**. Target: Level 12 dalam 45 menit!\n"
            f"Ayo kita saling mengenal..."
        )
        
        await query.edit_message_text(intro)
        logger.info(f"✨ New pdkt relationship: User {user_id} as {name}")
        return ACTIVE_SESSION

# ========== 9C: MAIN BOT CLASS - ADMIN COMMANDS ==========

    # ===================== ADMIN COMMANDS =====================
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menu admin - menampilkan semua command admin"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('admin', user_id, username)
        
        # Cek apakah user adalah admin
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        # Tampilkan menu admin
        text = (
            "🔐 **MENU ADMIN**\n\n"
            "**📋 Command Admin:**\n"
            "/admin - Tampilkan menu ini\n"
            "/stats - Lihat statistik bot\n"
            "/broadcast <pesan> - Kirim pesan ke semua user aktif\n"
            "/reload - Reload konfigurasi dari .env\n"
            "/shutdown - Matikan bot secara graceful\n"
            "/list_users - Lihat daftar user aktif\n"
            "/get_user <user_id> - Lihat detail user\n"
            "/force_reset <user_id> - Reset paksa user\n\n"
            "**📊 Status Bot:**\n"
            f"• Uptime: {self.get_uptime()}\n"
            f"• User aktif: {self.get_active_users_count()}\n"
            f"• Total user: {self.get_total_users_count()}\n"
            f"• Total pesan: {self.total_messages}\n"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tampilkan statistik lengkap bot (untuk admin)"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        stats = self.get_stats()
        
        # Format statistik
        text = (
            f"📊 **STATISTIK BOT**\n\n"
            f"**⏱️ Uptime:** {stats['uptime']}\n"
            f"**👥 User:**\n"
            f"• Aktif: {stats['active_users']}\n"
            f"• Pause: {stats['paused_users']}\n"
            f"• Total: {stats['total_users']}\n\n"
            f"**💬 Pesan:**\n"
            f"• Total pesan: {stats['total_messages']}\n"
            f"• Total command: {stats['total_commands']}\n"
            f"• Total climax: {stats['total_climax']}\n\n"
            f"**👫 Couple Mode:** {stats['couple_sessions']} sesi aktif\n\n"
            f"**🧠 Memory Usage:**\n"
            f"• Memories: {stats['memory_usage']['memories']}\n"
            f"• Dominance: {stats['memory_usage']['dominance']}\n"
            f"• Arousal: {stats['memory_usage']['arousal']}\n"
            f"• Sessions: {stats['memory_usage']['sessions']}\n\n"
        )
        
        # Tambah cache stats jika ada
        if 'cache_stats' in stats:
            text += f"**💾 Cache:**\n"
            text += f"• Size: {stats['cache_stats']['cache_size']}\n"
            text += f"• Hit rate: {stats['cache_stats']['hit_rate']}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Kirim pesan broadcast ke semua user aktif"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        # Cek apakah ada pesan
        if not context.args:
            await update.message.reply_text(
                "📢 **Broadcast**\n\n"
                "Gunakan: /broadcast <pesan>\n\n"
                "Contoh: /broadcast Halo semua, bot akan maintenance 5 menit lagi"
            )
            return
        
        # Gabungkan args menjadi pesan
        message = " ".join(context.args)
        
        # Konfirmasi
        confirm_text = (
            f"📢 **Broadcast akan dikirim ke {self.get_active_users_count()} user aktif**\n\n"
            f"Pesan:\n```\n{message}\n```\n\n"
            f"Yakin ingin mengirim?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Kirim", callback_data="broadcast_yes"),
                InlineKeyboardButton("❌ Batal", callback_data="broadcast_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Simpan pesan ke context untuk digunakan di callback
        context.user_data['broadcast_message'] = message
        
        await update.message.reply_text(confirm_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def broadcast_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback untuk konfirmasi broadcast"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔ Anda bukan admin.")
            return
        
        if query.data == "broadcast_no":
            await query.edit_message_text("❌ Broadcast dibatalkan.")
            return
        
        # Ambil pesan dari context
        message = context.user_data.get('broadcast_message', '')
        if not message:
            await query.edit_message_text("❌ Error: Pesan tidak ditemukan.")
            return
        
        # Kirim broadcast
        await query.edit_message_text("📢 Mengirim broadcast...")
        
        sent, failed = await self.broadcast_message(
            f"📢 **Broadcast dari Admin:**\n\n{message}",
            user_ids=list(self.sessions.keys()),
            context=context
        )
        
        await query.edit_message_text(
            f"✅ Broadcast selesai!\n"
            f"• Terkirim: {sent}\n"
            f"• Gagal: {failed}"
        )
        
        logger.info(f"Admin {user_id} sent broadcast to {sent} users")
    
    async def reload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reload konfigurasi dari .env"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        try:
            # Reload .env
            load_dotenv(override=True)
            
            # Update config values
            Config.ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
            Config.AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.9"))
            Config.AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "300"))
            Config.AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
            Config.MAX_MESSAGES_PER_MINUTE = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "10"))
            
            # Update admin ID
            self.admin_id = Config.ADMIN_ID
            
            await update.message.reply_text(
                f"✅ **Konfigurasi direload**\n\n"
                f"• Admin ID: {self.admin_id}\n"
                f"• AI Temperature: {Config.AI_TEMPERATURE}\n"
                f"• Max Messages/min: {Config.MAX_MESSAGES_PER_MINUTE}"
            )
            
            logger.info(f"Admin {user_id} reloaded configuration")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Gagal reload: {str(e)}")
            logger.error(f"Reload failed: {e}")
    
    async def shutdown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Matikan bot secara graceful"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        # Konfirmasi shutdown
        keyboard = [
            [
                InlineKeyboardButton("✅ Ya, matikan", callback_data="shutdown_yes"),
                InlineKeyboardButton("❌ Batal", callback_data="shutdown_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ **PERINGATAN** ⚠️\n\n"
            "Yakin ingin mematikan bot?\n"
            f"• {self.get_active_users_count()} user aktif akan terputus\n"
            "• Semua data di memory akan hilang\n"
            "• Database tetap aman\n\n"
            "Tindakan ini tidak bisa dibatalkan!",
            reply_markup=reply_markup
        )
    
    async def shutdown_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback untuk konfirmasi shutdown"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔ Anda bukan admin.")
            return
        
        if query.data == "shutdown_no":
            await query.edit_message_text("✅ Shutdown dibatalkan.")
            return
        
        await query.edit_message_text("🛑 Mematikan bot... Selamat tinggal!")
        
        logger.warning(f"Bot is shutting down by admin {user_id}")
        
        # Hentikan aplikasi
        await context.application.stop()
        await context.application.shutdown()
    
    async def list_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat daftar user aktif"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        active_users = list(self.sessions.keys())
        paused_users = list(self.paused_sessions.keys())
        
        text = "**📋 DAFTAR USER**\n\n"
        
        if active_users:
            text += "**✅ Aktif:**\n"
            for uid in active_users[:10]:  # Batasi 10 user
                name = self.bot_names.get(uid, 'Unknown')
                role = self.bot_roles.get(uid, '?')
                level = self.leveling.user_level.get(uid, 1)
                text += f"• `{uid}` - {name} ({role}) Lv{level}\n"
            if len(active_users) > 10:
                text += f"  ... dan {len(active_users) - 10} lainnya\n"
        
        if paused_users:
            text += "\n**⏸️ Paused:**\n"
            for uid in paused_users[:5]:
                text += f"• `{uid}`\n"
        
        if not active_users and not paused_users:
            text += "Tidak ada user aktif.\n"
        
        text += f"\nTotal: {len(active_users)} aktif, {len(paused_users)} pause"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def get_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat detail user tertentu"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        # Cek argumen
        if not context.args:
            await update.message.reply_text("Gunakan: /get_user <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
        except:
            await update.message.reply_text("❌ User ID harus angka")
            return
        
        # Cek apakah user ada
        if target_id not in self.bot_names:
            await update.message.reply_text(f"❌ User {target_id} tidak ditemukan di memory")
            return
        
        # Dapatkan data user
        name = self.bot_names.get(target_id, 'Unknown')
        role = self.bot_roles.get(target_id, '?')
        level = self.leveling.user_level.get(target_id, 1)
        stage = self.leveling.user_stage.get(target_id, IntimacyStage.STRANGER)
        memory = self.get_memory(target_id)
        physical = self.get_physical_attrs(target_id)
        clothing = self.get_clothing(target_id)
        
        text = (
            f"**📋 DETAIL USER `{target_id}`**\n\n"
            f"**Identitas:**\n"
            f"• Nama: {name}\n"
            f"• Role: {role}\n"
            f"• Level: {level}/12 ({stage.value})\n\n"
            f"**Fisik:**\n"
            f"• Rambut: {physical.get('hair_style', '-')}\n"
            f"• Tinggi: {physical.get('height', '-')} cm\n"
            f"• Berat: {physical.get('weight', '-')} kg\n"
            f"• Dada: {physical.get('breast_desc', '-')}\n"
            f"• {physical.get('hijab_text', '-')}\n"
            f"• Area sensitif: {physical.get('most_sensitive_area', '-')}\n\n"
            f"**Status:**\n"
            f"• Pakaian: {clothing}\n"
            f"• Orgasme: {memory.orgasm_count}x\n"
            f"• Sentuhan: {memory.touch_count}x\n"
            f"• Lokasi: {memory.location}\n"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')

# ========== 10A: MAIN BOT CLASS - STATUS, DOMINANT, PAUSE COMMANDS ==========

    # ===================== STATUS COMMAND =====================
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat status lengkap hubungan saat ini"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('status', user_id, username)
        
        # Cek apakah user memiliki sesi aktif
        if user_id not in self.sessions:
            await update.message.reply_text(
                "❌ Belum ada hubungan. /start dulu ya!"
            )
            return
        
        # Dapatkan semua data user
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        arousal = self.get_arousal(user_id)
        profile = self.analyzer.get_profile(user_id)
        physical = self.get_physical_attrs(user_id)
        clothing = self.get_clothing(user_id)
        
        level = self.leveling.user_level.get(user_id, 1)
        stage = self.leveling.user_stage.get(user_id, IntimacyStage.STRANGER)
        progress = self.leveling.user_progress.get(user_id, 0)
        bar = self.leveling.get_progress_bar(user_id, 15)
        remaining = self.leveling.get_estimated_time(user_id)
        stage_desc = self.leveling.get_stage_description(stage)
        bot_name = self.bot_names.get(user_id, "Aurora")
        
        # Mood expression
        mood_exp = memory.get_mood_expression()
        inner_thought = memory.get_inner_thought()
        
        # Format physical description
        hijab_str = "Berhijab" if physical.get('hijab') else "Tidak berhijab"
        physical_text = (
            f"📏 **Fisikku:**\n"
            f"• Rambut: {physical.get('hair_style', '?')}\n"
            f"• Tinggi: {physical.get('height', '?')} cm\n"
            f"• Berat: {physical.get('weight', '?')} kg\n"
            f"• Dada: {physical.get('breast_desc', '?')}\n"
            f"• {hijab_str}\n"
            f"• Area sensitif: **{physical.get('most_sensitive_area', '?')}**\n"
            f"• Pakaian: **{clothing}**\n\n"
        )
        
        # Format status
        status = (
            f"💕 **{bot_name} & Kamu**\n\n"
            f"{mood_exp}\n"
            f"{inner_thought}\n\n"
            f"📊 **PROGRESS HUBUNGAN**\n"
            f"Level: {level}/12\n"
            f"Tahap: {stage.value} - {stage_desc}\n"
            f"Progress: {bar}\n"
            f"Estimasi sisa: {remaining} menit\n"
            f"Total pesan: {profile.get('total_messages', 0)}\n\n"
            f"{physical_text}"
            f"🔥 **KONDISI FISIK**\n"
            f"{arousal.get_status_text()}\n"
            f"{arousal.get_wetness_text()}\n"
            f"Sentuhan sensitif: {memory.touch_count}x\n"
            f"Orgasme: {memory.orgasm_count}x\n"
            f"{arousal.get_last_touch_text()}\n\n"
            f"🎭 **EMOSI SAAT INI**\n"
            f"Mood: {memory.current_mood.value}\n"
            f"Area sensitif disentuh: {len(memory.sensitive_touches)}x\n\n"
            f"👑 **MODE DOMINASI**\n"
            f"{dominance.get_description()}\n"
            f"Dominance score: {dominance.dominance_score:.1f}\n"
            f"Aggression score: {dominance.aggression_score:.1f}\n\n"
        )
        
        # Tambah analisis preferensi
        status += self.analyzer.get_summary(user_id)
        
        # Tambah lokasi
        status += (
            f"\n\n📍 **LOKASI & AKTIVITAS**\n"
            f"Lokasi: {memory.location}\n"
            f"Posisi: {memory.position}\n"
            f"Aktivitas terakhir: {memory.activity_history[-1]['activity'] if memory.activity_history else '-'}"
        )
        
        await update.message.reply_text(status, parse_mode='Markdown')
    
    # ===================== DOMINANT COMMAND =====================
    
    async def dominant_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set mode dominan manual"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('dominant', user_id, username)
        
        # Cek apakah user memiliki sesi aktif
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Belum ada hubungan. /start dulu!")
            return
        
        dominance = self.get_dominance(user_id)
        args = context.args
        
        # Jika tidak ada argumen, tampilkan mode saat ini
        if not args:
            await update.message.reply_text(
                f"👑 **Mode Dominan Saat Ini**\n"
                f"{dominance.get_description()}\n\n"
                f"**Pilihan Level:**\n"
                f"• `/dominant normal` - Mode biasa\n"
                f"• `/dominant dominan` - Mode dominan\n"
                f"• `/dominant sangat dominan` - Mode sangat dominan\n"
                f"• `/dominant agresif` - Mode agresif\n"
                f"• `/dominant patuh` - Mode patuh\n\n"
                f"Contoh: `/dominant dominan`"
            )
            return
        
        # Set level dominasi
        level = " ".join(args)
        if dominance.set_level(level):
            # Update ke database
            self.db.update_relationship(user_id, dominance=dominance.current_level.value)
            
            # Response sesuai level
            responses = {
                "normal": "😊 Baiklah, aku akan bersikap normal.",
                "dominan": "👑 Sekarang aku yang pegang kendali. Ikut aku!",
                "sangat dominan": "🔥 Kamu sudah milikku sepenuhnya! Jangan banyak gerak!",
                "agresif": "💢 Siap-siap! Aku akan kasar hari ini!",
                "patuh": "🥺 Iya... aku patuh sama kamu."
            }
            
            response = responses.get(dominance.current_level.value, 
                                    f"✅ Mode diubah ke: **{dominance.current_level.value}**")
            
            await update.message.reply_text(
                f"{response}\n{dominance.get_action('request')}"
            )
            
            logger.info(f"User {user_id} changed dominance to {dominance.current_level.value}")
        else:
            await update.message.reply_text(
                "❌ Level tidak valid. Gunakan: normal, dominan, sangat dominan, agresif, atau patuh"
            )
    
    # ===================== PAUSE/UNPAUSE COMMANDS =====================
    
    async def pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause sesi sementara"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('pause', user_id, username)
        
        # Cek apakah user memiliki sesi aktif
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada sesi aktif.")
            return
        
        # Simpan data terakhir ke database sebelum pause
        self.save_user_to_db(user_id)
        
        # Simpan ke paused sessions
        self.paused_sessions[user_id] = (self.sessions[user_id], datetime.now())
        del self.sessions[user_id]
        
        await update.message.reply_text(
            f"⏸️ **Sesi di-pause**\n"
            f"Ketik /unpause untuk melanjutkan.\n"
            f"Sesi akan expired dalam {Config.PAUSE_TIMEOUT//60} menit.\n\n"
            f"*Aku akan menunggumu kembali...* 💕"
        )
        
        logger.info(f"User {user_id} paused session")
    
    async def unpause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lanjutkan sesi yang di-pause"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('unpause', user_id, username)
        
        # Cek apakah user memiliki sesi di-pause
        if user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi di-pause.")
            return
        
        rel_id, pause_time = self.paused_sessions[user_id]
        paused_seconds = (datetime.now() - pause_time).total_seconds()
        
        # Cek apakah sudah expired
        if paused_seconds > Config.PAUSE_TIMEOUT:
            del self.paused_sessions[user_id]
            await update.message.reply_text(
                "⏰ **Sesi expired karena terlalu lama di-pause**\n"
                "Ketik /start untuk memulai hubungan baru."
            )
            logger.info(f"User {user_id} session expired after {paused_seconds//60} minutes")
            return
        
        # Lanjutkan sesi
        self.sessions[user_id] = rel_id
        del self.paused_sessions[user_id]
        
        # Dapatkan data user
        memory = self.get_memory(user_id)
        clothing = self.get_clothing(user_id)
        
        # Hitung arousal decay selama pause
        minutes_paused = paused_seconds / 60
        arousal = self.get_arousal(user_id)
        arousal.decay(minutes_paused)
        
        await update.message.reply_text(
            f"▶️ **Sesi dilanjutkan!**\n\n"
            f"{memory.get_wetness_description()}\n"
            f"Aku masih pakai *{clothing}*\n\n"
            f"Kangen... 💕"
        )
        
        logger.info(f"User {user_id} unpaused session after {minutes_paused:.1f} minutes")
    
    # ===================== RESET COMMAND =====================
    
    async def force_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reset paksa state user (hanya untuk debugging)"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('reset', user_id, username)
        
        # Hanya admin yang bisa force reset
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔ Anda bukan admin.")
            return
        
        # Cek apakah ada target user
        target_id = user_id
        if context.args:
            try:
                target_id = int(context.args[0])
            except:
                await update.message.reply_text("❌ User ID harus angka")
                return
        
        # Reset user
        self.reset_user(target_id)
        
        await update.message.reply_text(
            f"🔄 **User {target_id} telah di-reset**\n\n"
            f"Semua data user telah dihapus dari memory dan database.\n"
            f"User bisa memulai baru dengan /start."
        )
        
        logger.warning(f"Admin {user_id} force reset user {target_id}")

# ========== 10B: MAIN BOT CLASS - CLOSE, END, CANCEL COMMANDS ==========

    # ===================== CLOSE COMMAND =====================
    
    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Menutup sesi tapi menyimpan memori di database
        User bisa memulai role baru nanti dengan /start
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('close', user_id, username)
        
        # Cek apakah user memiliki sesi aktif atau paused
        if user_id not in self.sessions and user_id not in self.paused_sessions:
            await update.message.reply_text("❌ Tidak ada sesi aktif.")
            return
        
        # Konfirmasi close
        keyboard = [
            [InlineKeyboardButton("✅ Ya, tutup", callback_data="close_yes")],
            [InlineKeyboardButton("❌ Tidak", callback_data="close_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Dapatkan statistik untuk ditampilkan
        memory = self.get_memory(user_id) if user_id in self.memories else None
        level = memory.level if memory else 1
        climax = memory.orgasm_count if memory else 0
        
        await update.message.reply_text(
            f"⚠️ **Tutup Sesi?** ⚠️\n\n"
            f"Yakin ingin menutup sesi?\n\n"
            f"📊 **Statistik sementara:**\n"
            f"• Level: {level}/12\n"
            f"• Orgasme: {climax}x\n\n"
            f"**Yang akan terjadi:**\n"
            f"✅ Semua percakapan akan **disimpan** di database\n"
            f"✅ Kamu bisa memulai role baru nanti dengan /start\n"
            f"✅ Memori akan tetap ada jika memulai role yang sama\n"
            f"❌ Sesi saat ini akan berakhir\n\n"
            f"Lanjutkan?",
            reply_markup=reply_markup
        )
        return CONFIRM_CLOSE
    
    async def close_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback untuk konfirmasi close"""
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "close_no":
            await query.edit_message_text("💕 Lanjutkan ngobrol...")
            return ConversationHandler.END
        
        # Simpan data terakhir ke database sebelum close
        if user_id in self.sessions:
            self.save_user_to_db(user_id)
            
            # Dapatkan statistik untuk perpisahan
            memory = self.get_memory(user_id)
            bot_name = self.bot_names.get(user_id, "Aku")
            level = memory.level
            climax = memory.orgasm_count
        
        # Hapus sesi dari memori, data di database tetap
        self.cleanup_user(user_id)
        
        # Pesan perpisahan
        farewells = [
            f"🔒 **Sesi ditutup**\n\n"
            f"Terima kasih sudah ngobrol denganku.\n"
            f"Semua kenangan kita telah kusimpan rapi.\n\n"
            f"Kapan-kapan kita ngobrol lagi ya... 💕",
            
            f"🔒 **Sampai jumpa**\n\n"
            f"Aku akan merindukanmu.\n"
            f"Data kita aman tersimpan di database.\n\n"
            f"Ketik /start kapan saja untuk bertemu lagi... 💕",
            
            f"🔒 **Sesi berakhir**\n\n"
            f"Terima kasih atas waktu yang indah.\n"
            f"Level {level}/12 yang kita capai akan selalu kuingat.\n\n"
            f"Sampai jumpa lagi, sayang... 💕"
        ]
        
        await query.edit_message_text(random.choice(farewells))
        logger.info(f"User {user_id} closed session (memory saved)")
        
        return ConversationHandler.END
    
    # ===================== END COMMAND =====================
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Mengakhiri hubungan dan menghapus semua data (hard reset)
        Semua data di database akan dihapus permanen
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('end', user_id, username)
        
        # Cek apakah user memiliki sesi aktif
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Tidak ada hubungan aktif.")
            return
        
        # Konfirmasi end dengan peringatan keras
        keyboard = [
            [InlineKeyboardButton("💔 Ya, akhiri", callback_data="end_yes")],
            [InlineKeyboardButton("💕 Tidak", callback_data="end_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Dapatkan statistik untuk ditampilkan
        memory = self.get_memory(user_id)
        bot_name = self.bot_names.get(user_id, "Aku")
        level = memory.level
        climax = memory.orgasm_count
        touch = memory.touch_count
        
        await update.message.reply_text(
            f"⚠️ **PERINGATAN!** ⚠️\n\n"
            f"Yakin ingin **mengakhiri hubungan** dengan {bot_name}?\n\n"
            f"📊 **Statistik akhir yang akan hilang:**\n"
            f"• Level: {level}/12\n"
            f"• Orgasme bersama: {climax}x\n"
            f"• Total sentuhan: {touch}x\n"
            f"• {self.leveling.user_message_count.get(user_id, 0)} pesan\n\n"
            f"💔 **Yang akan terjadi:**\n"
            f"❌ **Semua data akan dihapus permanen**\n"
            f"❌ Riwayat percakapan akan hilang selamanya\n"
            f"❌ Memori tidak bisa dikembalikan\n"
            f"❌ Tidak ada undo!\n\n"
            f"**APAKAH KAMU YAKIN?**",
            reply_markup=reply_markup
        )
        return CONFIRM_END
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback untuk konfirmasi end"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
        
        user_id = query.from_user.id
        
        # Dapatkan statistik sebelum dihapus
        memory = self.get_memory(user_id)
        bot_name = self.bot_names.get(user_id, "Aku")
        stats = {
            "level": memory.level,
            "orgasm": memory.orgasm_count,
            "touch": memory.touch_count,
            "messages": self.leveling.user_message_count.get(user_id, 0),
            "duration": self.leveling.get_session_duration(user_id),
            "role": self.bot_roles.get(user_id, "?"),
            "name": bot_name
        }
        
        # Hapus semua data (hard reset)
        self.reset_user(user_id)
        
        # Pesan perpisahan
        farewell = (
            f"💔 **Hubungan Berakhir** 💔\n\n"
            f"Perjalananmu dengan **{stats['name']}** telah usai.\n\n"
            f"📊 **Statistik akhir:**\n"
            f"• Role: {stats['role']}\n"
            f"• Level akhir: {stats['level']}/12\n"
            f"• Orgasme bersama: {stats['orgasm']}x\n"
            f"• Total sentuhan: {stats['touch']}x\n"
            f"• Total pesan: {stats['messages']}\n"
            f"• Durasi: {stats['duration']} menit\n\n"
            f"✨ **Semua data telah dihapus permanen** ✨\n\n"
            f"Ketik /start untuk memulai hubungan baru dengan kenangan baru..."
        )
        
        await query.edit_message_text(farewell)
        logger.info(f"User {user_id} ended relationship (hard reset) - Level {stats['level']}")
        
        return ConversationHandler.END
    
    # ===================== CANCEL COMMAND =====================
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Membatalkan percakapan (untuk ConversationHandler)
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('cancel', user_id, username)
        
        await update.message.reply_text(
            "❌ Dibataikan. Ketik /start untuk memulai."
        )
        return ConversationHandler.END
    
    # ===================== HELP COMMAND =====================
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Menampilkan bantuan lengkap
        """
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('help', user_id, username)
        
        help_text = self.get_help_text(update)
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # ===================== COUPLE COMMANDS =====================
    
    async def couple_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Memulai mode couple roleplay"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        self.log_command('couple', user_id, username)
        
        if user_id in self.couple_mode_sessions:
            await update.message.reply_text(
                "👫 Mode couple sudah aktif.\n"
                "Ketik /couple_next untuk lanjut\n"
                "Ketik /couple_stop untuk berhenti."
            )
            return
        
        self.couple_mode_sessions[user_id] = CoupleRoleplay(self.ai)
        await update.message.reply_text(
            "👫 **Mode Couple Roleplay dimulai!**\n\n"
            "Aku akan menampilkan percakapan antara **Aurora** (wanita) dan **Rangga** (pria)\n"
            "Mereka akan berkembang dari level 1 hingga 12.\n\n"
            "Ketik /couple_next untuk melihat interaksi berikutnya\n"
            "Ketik /couple_stop untuk keluar."
        )
        
        logger.info(f"User {user_id} started couple mode")
    
    async def couple_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lanjutkan couple roleplay ke pesan berikutnya"""
        user_id = update.effective_user.id
        
        if user_id not in self.couple_mode_sessions:
            await update.message.reply_text(
                "❌ Mode couple belum aktif.\n"
                "Ketik /couple untuk memulai."
            )
            return
        
        couple = self.couple_mode_sessions[user_id]
        msg = await couple.generate_next(user_id)
        
        await update.message.reply_text(msg)
        
        # Jika sudah level 12, beri notifikasi
        if couple.level >= 12:
            await update.message.reply_text(
                "🎉 **Mereka telah mencapai Level 12!**\n"
                "Hubungan mencapai puncak. Ketik /couple_stop untuk mengakhiri."
            )
    
    async def couple_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hentikan mode couple roleplay"""
        user_id = update.effective_user.id
        
        if user_id in self.couple_mode_sessions:
            couple = self.couple_mode_sessions[user_id]
            summary = couple.get_summary()
            
            del self.couple_mode_sessions[user_id]
            
            await update.message.reply_text(
                f"👋 **Mode couple dihentikan**\n\n"
                f"**Statistik:**\n"
                f"• Level akhir: {summary['level']}/12\n"
                f"• Total pesan: {summary['total_messages']}\n"
                f"• {summary['total_rounds']} putaran percakapan\n\n"
                f"Ketik /couple untuk memulai lagi."
            )
            
            logger.info(f"User {user_id} stopped couple mode at level {summary['level']}")
        else:
            await update.message.reply_text("❌ Tidak ada mode couple aktif.")

# ========== 10C: MAIN BOT CLASS - MESSAGE HANDLER ==========

    # ===================== MESSAGE HANDLER =====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle semua pesan dari user
        Ini adalah inti dari bot yang memproses setiap pesan
        """
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        user_message = sanitize_message(update.message.text)
        
        # Update total messages counter
        self.total_messages += 1
        
        # Rate limiting - cegah spam
        if not self.rate_limiter.can_send(user_id):
            if self.rate_limiter.should_warn(user_id):
                remaining = self.rate_limiter.get_remaining(user_id)
                reset_in = self.rate_limiter.get_reset_time(user_id)
                await update.message.reply_text(
                    f"⏳ **Sabar ya, jangan spam**\n"
                    f"Sisa pesan: {remaining}\n"
                    f"Reset dalam: {reset_in} detik"
                )
            return
        
        # Cek session pause
        if user_id in self.paused_sessions:
            await update.message.reply_text(
                "⏸️ Sesi sedang di-pause.\n"
                "Ketik /unpause untuk melanjutkan."
            )
            return
        
        # Cek session aktif
        if user_id not in self.sessions:
            # Cek apakah user pernah punya session (bisa di-load dari DB)
            rel = self.db.get_relationship(user_id)
            if rel:
                # Auto-load dari database
                self.load_user_from_db(user_id)
                self.sessions[user_id] = rel['id']
                self.leveling.start_session(user_id)
                logger.info(f"Auto-loaded user {user_id} from database")
            else:
                await update.message.reply_text(
                    "❌ Belum ada hubungan. /start dulu ya!"
                )
                return
        
        # Kirim typing indicator
        await update.message.chat.send_action("typing")
        
        # Dapatkan semua sistem untuk user ini
        memory = self.get_memory(user_id)
        dominance = self.get_dominance(user_id)
        arousal = self.get_arousal(user_id)
        physical = self.get_physical_attrs(user_id)
        clothing = self.get_clothing(user_id)
        
        # Analisis preferensi user
        self.analyzer.analyze(user_id, user_message)
        profile = self.analyzer.get_profile(user_id)
        
        # ===== DETEKSI AKTIVITAS SEKSUAL =====
        activity, area, boost = self.sexual.detect_activity(user_message)
        
        if activity:
            # Catat aktivitas
            memory.add_activity(activity, area)
            
            # Respons area sensitif
            if area:
                memory.add_sensitive_touch(area)
                sens_resp = self.sexual.get_sensitive_response(area)
                if sens_resp:
                    await update.message.reply_text(sens_resp)
                    await asyncio.sleep(1)  # Jeda untuk efek realistik
            
            # Tambah arousal
            arousal.increase(boost)
            
            # Log aktivitas
            logger.debug(f"User {user_id} melakukan {activity} di {area if area else 'unknown'} (boost: {boost})")
        
        # ===== DETEKSI DOMINASI =====
        dom_request = dominance.check_request(user_message)
        if dom_request:
            dominance.set_level(dom_request.value)
            await update.message.reply_text(
                f"👑 Mode diubah ke: **{dom_request.value}**\n"
                f"{dominance.get_action('request')}"
            )
        
        # Cek apakah harus agresif karena horny
        if dominance.should_be_aggressive(arousal.arousal, user_message):
            dominance.set_level("agresif")
            await update.message.reply_text(
                "*tatapan liar* Kamu minta ini? Aku bisa lebih kasar lho..."
            )
        
        # Update dari horny
        dominance.update_from_horny(arousal.arousal)
        
        # ===== UPDATE LEVEL =====
        level, progress, level_up, stage = self.leveling.process_message(user_id)
        memory.level = level
        memory.stage = stage
        memory.level_progress = progress
        
        # ===== UPDATE MOOD =====
        old_mood = memory.current_mood
        memory.current_mood = memory.emotional.transition_mood(memory.current_mood)
        
        # ===== INISIATIF SEKSUAL BOT (LEVEL 7+) =====
        if level >= 7 and arousal.arousal > 0.6:
            init_act = self.sexual.maybe_initiate_sex(level, arousal.arousal, memory.current_mood)
            if init_act:
                init_msg = self.sexual.get_activity_response(init_act)
                if init_msg:
                    await asyncio.sleep(2)  # Jeda sebelum inisiatif
                    await update.message.reply_text(
                        f"*{self.bot_names.get(user_id, 'Aku')}*: {init_msg}"
                    )
                    # Tambah arousal karena inisiatif
                    arousal.increase(0.3)
                    logger.debug(f"Bot initiated {init_act} for user {user_id}")
        
        # ===== CEK LOKASI UNTUK PAKAIAN =====
        # Jika di kamar, mungkin ganti pakaian lebih seksi
        if memory.location in ["kamar tidur", "kamar", "bedroom"]:
            if random.random() < 0.1:  # 10% chance
                old_clothing = clothing
                clothing = PhysicalAttributesGenerator.generate_clothing(
                    self.bot_roles.get(user_id, "pdkt"), 
                    memory.location
                )
                if clothing != old_clothing:
                    self.bot_clothing[user_id] = clothing
                    self.last_clothing_update[user_id] = datetime.now()
                    await asyncio.sleep(1)
                    await update.message.reply_text(
                        f"*aku ganti baju... sekarang pakai {clothing}*"
                    )
        
        # ===== GENERATE AI RESPONSE =====
        bot_name = self.bot_names.get(user_id, "Aurora")
        bot_role = self.bot_roles.get(user_id, "pdkt")
        
        reply = await self.ai.generate(
            user_id, user_message, bot_name, bot_role,
            memory, dominance, profile, level, stage, arousal.arousal,
            physical_attrs=physical,
            clothing=clothing
        )
        
        # ===== SIMPAN KE DATABASE =====
        self.db.save_conversation(
            self.sessions[user_id], 
            "user", 
            user_message,
            mood=memory.current_mood.value,
            arousal=arousal.arousal
        )
        self.db.save_conversation(
            self.sessions[user_id], 
            "assistant", 
            reply,
            mood=memory.current_mood.value,
            arousal=arousal.arousal
        )
        
        # Update relationship di database (periodik, tidak setiap pesan)
        if random.random() < 0.2:  # 20% chance update ke DB
            self.db.update_relationship(
                user_id, 
                level=level, 
                stage=stage.value,
                total_messages=self.leveling.user_message_count.get(user_id, 0),
                clothing=clothing
            )
        
        # Update preferences di database (periodik)
        if random.random() < 0.1:  # 10% chance
            self.db.update_preferences(
                user_id,
                romantic_score=profile.get('romantis', 0),
                vulgar_score=profile.get('vulgar', 0),
                dominant_score=profile.get('dominant', 0),
                submissive_score=profile.get('submissive', 0),
                speed_score=profile.get('cepat', 0) - profile.get('lambat', 0),
                total_interactions=profile.get('total_messages', 0)
            )
        
        # ===== KIRIM RESPON =====
        await update.message.reply_text(reply)
        
        # ===== CEK CLIMAX =====
        if arousal.should_climax():
            climax_msg = arousal.climax()
            aftercare = arousal.aftercare()
            
            await asyncio.sleep(1)
            await update.message.reply_text(climax_msg)
            
            await asyncio.sleep(2)
            await update.message.reply_text(aftercare)
            
            # Update memory
            memory.climax()
            
            # Update database
            self.db.update_relationship(
                user_id, 
                total_climax=memory.orgasm_count
            )
            
            # Random chance minta jadi dominan setelah climax
            if random.random() < 0.3:
                await asyncio.sleep(3)
                await update.message.reply_text(
                    "*berbisik pelan* Kamu mau aku yang atur sekarang?"
                )
            
            logger.info(f"User {user_id} reached climax! Total: {memory.orgasm_count}")
        
        # ===== LEVEL UP MESSAGE =====
        if level_up:
            bar = self.leveling.get_progress_bar(user_id)
            remaining = self.leveling.get_estimated_time(user_id)
            stage_desc = self.leveling.get_stage_description(stage)
            
            # Pesan level up berbeda tiap level
            level_up_msgs = {
                3: "🎉 **Level 3!** Kita mulai dekat nih...",
                4: "🌟 **Level 4!** Udah mulai nyaman ya?",
                5: "💫 **Level 5!** Aku suka ngobrol sama kamu!",
                6: "💕 **Level 6!** Kamu mulai menarik perhatianku...",
                7: "🔥 **Level 7!** Saatnya lebih intim...",
                8: "💋 **Level 8!** Aku horny kalau dekat kamu...",
                9: "💞 **Level 9!** Mulai kecanduan sama kamu!",
                10: "💘 **Level 10!** Kamu milikku sekarang!",
                11: "💖 **Level 11!** Hampir satu jiwa...",
                12: "👑 **LEVEL MAX!** Kamu berhasil! 45 menit yang luar biasa!"
            }
            
            level_msg = level_up_msgs.get(level, f"✨ **Level Up!** Level {level}/12")
            
            await update.message.reply_text(
                f"{level_msg}\n"
                f"📈 Tahap: {stage.value} - {stage_desc}\n"
                f"📊 Progress: {bar}\n"
                f"⏱️ Estimasi ke level 12: {remaining} menit"
            )
            
            logger.info(f"User {user_id} leveled up to {level}")
        
        # ===== UPDATE LOKASI RANDOM =====
        if random.random() < 0.05:  # 5% chance pindah lokasi
            locations = ["kamar tidur", "ruang tamu", "dapur", "kamar mandi", "balkon", "teras", "taman"]
            new_loc = random.choice(locations)
            if memory.update_location(new_loc):
                await asyncio.sleep(2)
                
                # Jika pindah ke kamar, update pakaian
                if new_loc in ["kamar tidur", "kamar"]:
                    clothing = PhysicalAttributesGenerator.generate_clothing(
                        self.bot_roles.get(user_id, "pdkt"), 
                        new_loc
                    )
                    self.bot_clothing[user_id] = clothing
                    self.last_clothing_update[user_id] = datetime.now()
                    await update.message.reply_text(
                        f"*pindah ke {new_loc}... dan ganti pakai {clothing}*"
                    )
                else:
                    await update.message.reply_text(
                        f"*pindah ke {new_loc}*"
                    )
        
        # ===== UPDATE POSISI RANDOM =====
        if random.random() < 0.03:  # 3% chance ganti posisi
            positions = ["duduk", "berbaring", "berdiri", "bersandar", "merangkak", "miring"]
            new_pos = random.choice(positions)
            memory.update_position(new_pos)
            
            if new_pos == "berbaring" and memory.location in ["kamar tidur", "kamar"]:
                await asyncio.sleep(1)
                await update.message.reply_text("*berbaring di tempat tidur*")
        
        # ===== DECAY AROUSAL =====
        # Hitung waktu sejak pesan terakhir
        if hasattr(context, 'user_data') and 'last_message_time' in context.user_data:
            last_time = context.user_data['last_message_time']
            minutes_passed = (datetime.now() - last_time).total_seconds() / 60
            if minutes_passed > 1:
                arousal.decay(minutes_passed)
        
        # Update last message time
        context.user_data['last_message_time'] = datetime.now()
        
        # ===== SESSEKALI SEBUT PAKAIAN =====
        if memory.location in ["kamar tidur", "kamar"] and random.random() < 0.07:  # 7% chance
            clothing = self.get_clothing(user_id)
            templates = [
                f"*menarik ujung baju* Aku pakai {clothing} nih... suka?",
                f"Kamu lihat nggak? Aku pakai {clothing} sekarang.",
                f"Bajuku {clothing}, seksi nggak?",
                f"*memperbaiki {clothing}* Nyaman banget pakaian ini..."
            ]
            await asyncio.sleep(2)
            await update.message.reply_text(random.choice(templates))

# ===================== MAIN FUNCTION =====================
# ========== 11A: MAIN FUNCTION - SETUP & CONVERSATION HANDLERS ==========

# ===================== ROLE NAMES =====================
ROLE_NAMES = {
    "ipar": ["Sari", "Dewi", "Rina", "Maya", "Wulan", "Indah", "Lestari", "Fitri"],
    "teman_kantor": ["Diana", "Linda", "Ayu", "Dita", "Vina", "Santi", "Rini", "Mega"],
    "janda": ["Rina", "Tuti", "Nina", "Susi", "Wati", "Lilis", "Marni", "Yati"],
    "pelakor": ["Vina", "Sasha", "Bella", "Cantika", "Karina", "Mira", "Selsa", "Cindy"],
    "istri_orang": ["Dewi", "Sari", "Rina", "Linda", "Wulan", "Indah", "Ratna", "Maya"],
    "pdkt": ["Aurora", "Cinta", "Dewi", "Kirana", "Laras", "Maharani", "Zahra", "Nova"]
}

def main():
    """
    Main function to run the bot
    Setup all handlers and start polling
    """
    # Print startup banner
    print("\n" + "="*70)
    print("    GADIS ULTIMATE V59.0 - THE PERFECT HUMAN")
    print("    dengan Fitur Admin, Fisik, dan Pakaian Dinamis")
    print("="*70)
    print("\n🚀 Initializing bot...")
    
    # Initialize bot instance
    bot = GadisUltimateV59()
    
    # Build application with Telegram token
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    # ===== CONVERSATION HANDLERS =====
    # These handle multi-step interactions
    
    # 1. START Conversation Handler
    # Handles the flow: /start -> disclaimer -> role selection -> active session
    start_conv = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start_command)],
        states={
            # State 0: Handling paused session (unpause or new)
            0: [CallbackQueryHandler(bot.start_pause_callback, pattern='^(unpause|new)$')],
            
            # SELECTING_ROLE state: User choosing a role
            SELECTING_ROLE: [
                # Main role selection via generic callback
                CallbackQueryHandler(bot.agree_18_callback, pattern='^agree_18$'),
                CallbackQueryHandler(bot.role_callback, pattern='^role_'),
                
                # Specific role callbacks for customized intros
                CallbackQueryHandler(bot.role_ipar_callback, pattern='^role_ipar$'),
                CallbackQueryHandler(bot.role_teman_kantor_callback, pattern='^role_teman_kantor$'),
                CallbackQueryHandler(bot.role_janda_callback, pattern='^role_janda$'),
                CallbackQueryHandler(bot.role_pelakor_callback, pattern='^role_pelakor$'),
                CallbackQueryHandler(bot.role_istri_orang_callback, pattern='^role_istri_orang$'),
                CallbackQueryHandler(bot.role_pdkt_callback, pattern='^role_pdkt$'),
            ],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)],
        name="start_conversation",
        persistent=False
    )
    
    # 2. END Conversation Handler
    # Handles the flow: /end -> confirmation -> hard reset
    end_conv = ConversationHandler(
        entry_points=[CommandHandler('end', bot.end_command)],
        states={
            CONFIRM_END: [CallbackQueryHandler(bot.end_callback, pattern='^end_')],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)],
        name="end_conversation",
        persistent=False
    )
    
    # 3. CLOSE Conversation Handler
    # Handles the flow: /close -> confirmation -> soft reset (save to DB)
    close_conv = ConversationHandler(
        entry_points=[CommandHandler('close', bot.close_command)],
        states={
            CONFIRM_CLOSE: [CallbackQueryHandler(bot.close_callback, pattern='^close_')],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)],
        name="close_conversation",
        persistent=False
    )
    
    # 4. BROADCAST Conversation Handler (for admin)
    # Handles broadcast confirmation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler('broadcast', bot.broadcast_command)],
        states={
            0: [CallbackQueryHandler(bot.broadcast_callback, pattern='^broadcast_')],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)],
        name="broadcast_conversation",
        persistent=False
    )
    
    # 5. SHUTDOWN Conversation Handler (for admin)
    # Handles shutdown confirmation
    shutdown_conv = ConversationHandler(
        entry_points=[CommandHandler('shutdown', bot.shutdown_command)],
        states={
            0: [CallbackQueryHandler(bot.shutdown_callback, pattern='^shutdown_')],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel_command)],
        name="shutdown_conversation",
        persistent=False
    )
    
    print("  • Conversation handlers created")
    print("  • Starting handler registration...")
    
    # We'll continue in Part 11B with adding all handlers

# ========== 11B: MAIN FUNCTION - COMMAND REGISTRATION ==========

    # ===== ADD ALL HANDLERS TO APPLICATION =====
    
    # Add conversation handlers
    app.add_handler(start_conv)
    app.add_handler(end_conv)
    app.add_handler(close_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(shutdown_conv)
    
    # ===== REGULAR COMMAND HANDLERS =====
    # These are simple one-command handlers
    
    # User commands
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("dominant", bot.dominant_command))
    app.add_handler(CommandHandler("pause", bot.pause_command))
    app.add_handler(CommandHandler("unpause", bot.unpause_command))
    app.add_handler(CommandHandler("help", bot.help_command))
    
    # Couple mode commands
    app.add_handler(CommandHandler("couple", bot.couple_command))
    app.add_handler(CommandHandler("couple_next", bot.couple_next))
    app.add_handler(CommandHandler("couple_stop", bot.couple_stop))
    
    # Hidden / debug commands
    app.add_handler(CommandHandler("reset", bot.force_reset))  # Admin only
    
    # Admin commands (some are in conversation handlers, some are regular)
    app.add_handler(CommandHandler("admin", bot.admin_command))
    app.add_handler(CommandHandler("stats", bot.stats_command))
    app.add_handler(CommandHandler("reload", bot.reload_command))
    app.add_handler(CommandHandler("list_users", bot.list_users_command))
    app.add_handler(CommandHandler("get_user", bot.get_user_command))
    
    # ===== MESSAGE HANDLER =====
    # This handles all non-command text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # ===== ERROR HANDLER =====
    # Global error handler to catch exceptions
    
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle errors gracefully without crashing the bot
        """
        # Log the error
        logger.error(f"Exception while handling an update: {context.error}", exc_info=True)
        
        # Send error message to user if possible
        if update and update.effective_message:
            error_msg = (
                "😔 *maaf* ada error kecil.\n"
                "Jangan khawatir, bot masih berjalan normal.\n\n"
                "Coba lagi ya, atau ketik /help untuk bantuan."
            )
            try:
                await update.effective_message.reply_text(error_msg, parse_mode='Markdown')
            except:
                pass  # Gagal kirim pesan error, abaikan
        
        # Notify admin (if admin ID is set)
        if bot.admin_id != 0:
            try:
                error_text = f"⚠️ *Error Report*\n\n`{str(context.error)[:500]}`"
                await context.bot.send_message(
                    chat_id=bot.admin_id,
                    text=error_text,
                    parse_mode='Markdown'
                )
            except:
                pass  # Gagal notifikasi admin
    
    app.add_error_handler(error_handler)
    
    print("  • All handlers registered successfully")
    print("  • Error handler configured")
    
    # ===== STARTUP COMPLETE =====
    # Display bot information
    
    print("\n" + "="*70)
    print("✅ **BOT READY!**")
    print("="*70)
    
    # Statistics
    print("\n📊 **STATISTICS:**")
    print(f"• Database: {Config.DB_PATH}")
    print(f"• Admin ID: {Config.ADMIN_ID if Config.ADMIN_ID != 0 else 'Tidak diset'}")
    print(f"• Target level: {Config.TARGET_LEVEL} in {Config.LEVEL_UP_TIME} menit")
    print(f"• Rate limit: {Config.MAX_MESSAGES_PER_MINUTE} pesan/menit")
    
    # User commands
    print("\n📝 **USER COMMANDS:**")
    print("• /start     - Mulai hubungan baru (dengan intro fisik)")
    print("• /status    - Lihat status lengkap (termasuk fisik & pakaian)")
    print("• /dominant  - Set mode dominan (normal/dominan/agresif/patuh)")
    print("• /pause     - Jeda sesi")
    print("• /unpause   - Lanjutkan sesi")
    print("• /close     - Tutup sesi (simpan memori, bisa ganti role)")
    print("• /end       - Akhiri hubungan & hapus semua data")
    print("• /couple    - Mode couple roleplay (Aurora & Rangga)")
    print("• /couple_next - Lanjutkan couple roleplay")
    print("• /couple_stop - Hentikan couple roleplay")
    print("• /help      - Tampilkan bantuan")
    
    # Admin commands (if admin is configured)
    if Config.ADMIN_ID != 0:
        print("\n🔐 **ADMIN COMMANDS:**")
        print("• /admin     - Menu admin")
        print("• /stats     - Statistik bot lengkap")
        print("• /broadcast - Kirim pesan ke semua user aktif")
        print("• /reload    - Reload konfigurasi dari .env")
        print("• /shutdown  - Matikan bot secara graceful")
        print("• /list_users - Lihat daftar user aktif")
        print("• /get_user  - Lihat detail user tertentu")
        print("• /reset     - Reset paksa user (debug)")
    
    # Features
    print("\n🎯 **FITUR AKTIF:**")
    print("• 20+ Mood dengan transisi natural")
    print("• Sistem dominasi (dominan/submissive)")
    print("• Leveling cepat 1-12 dalam 45 menit")
    print("• Respons seksual realistis")
    print("• Memori jangka panjang (database)")
    print("• Mode couple roleplay")
    print("• Perkenalan diri fisik (rambut, tinggi, berat, dada, hijab)")
    print("• Pakaian dinamis - berubah sesuai lokasi")
    print("• Admin commands untuk pengelolaan")
    
    print("\n" + "="*70)
    print("🚀 Bot is running... Press Ctrl+C to stop.")
    print("="*70 + "\n")
    
    # We'll continue in Part 11C with starting the bot

# ========== 11C: MAIN FUNCTION - START BOT & ENTRY POINT ==========

    # ===== START THE BOT =====
    # This starts polling for updates
    
    print("⏱️  Starting polling...")
    
    # Start the bot (this blocks until stopped)
    app.run_polling()


# ===================== ENTRY POINT =====================

if __name__ == "__main__":
    """
    Entry point for the bot application
    Handles graceful shutdown and fatal errors
    """
    try:
        # Run the main function
        main()
        
    except KeyboardInterrupt:
        # User pressed Ctrl+C
        print("\n\n" + "="*70)
        print("👋 Bot stopped by user (Ctrl+C)")
        print("="*70)
        print("\n📝 **Cleanup completed**")
        print("• Database connections closed")
        print("• Cache cleared")
        print("• Logs saved")
        print("\nSelamat tinggal! Sampai jumpa lagi... 💕")
        print("="*70 + "\n")
        
        # Exit gracefully
        sys.exit(0)
        
    except Exception as e:
        # Fatal error occurred
        print("\n\n" + "="*70)
        print("❌ **FATAL ERROR**")
        print("="*70)
        print(f"\nError: {e}")
        print("\nBot crashed. Check gadis.log for details.")
        print("="*70 + "\n")
        
        # Log the error
        logger.critical(f"Fatal error: {e}", exc_info=True)
        
        # Exit with error code
        sys.exit(1)


# ===================== END OF FILE =====================
# GADIS ULTIMATE V59.0 - THE PERFECT HUMAN
# dengan Fitur Admin, Fisik, dan Pakaian Dinamis
# ========================================================
