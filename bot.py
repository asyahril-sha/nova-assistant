"""
GADIS ULTIMATE V50.0 - SPEED SOUL BOUNDER EDITION
Fitur:
- START AT LEVEL 7: Langsung intim!
- FAST RESPONSE: Cepat merespon ajakan
- EASILY AROUSED: Horny dalam 1-2 sentuhan
- WORD ANALYZER: Analisis kata untuk percepat bonding
"""

import os
import logging
import json
import random
import asyncio
import sqlite3
import uuid
import threading
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import sys
from enum import Enum

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# OpenAI (DeepSeek)
from openai import OpenAI

# Voice (optional)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# ===================== KONFIGURASI =====================

DB_PATH = "gadis_v50.db"
START_LEVEL = 7  # Semua role langsung dari level 7!
LEVEL_UP_SPEED = 2.5  # 2.5x lebih cepat
HORNY_TRIGGER_COUNT = 2  # Jadi horny dalam 2 sentuhan

# State definitions
(SELECTING_ROLE, ACTIVE_SESSION) = range(2)

# ===================== ENUMS =====================

class Mood(Enum):
    CHERIA = "ceria"
    ROMANTIS = "romantis"
    HORNY = "horny"
    MARAH = "marah"
    LEMBUT = "lembut"

class IntimacyStage(Enum):
    INTIMATE = "intimate"      # Level 7-8
    OBSESSED = "obsessed"      # Level 9-10
    SOUL_BONDED = "soul_bonded" # Level 11
    AFTERCARE = "aftercare"     # Level 12

# ===================== WORD ANALYZER =====================

class WordAnalyzer:
    """
    Menganalisis setiap kata untuk mempercepat bonding dan arousal
    """
    
    def __init__(self):
        # Kata-kata yang memicu arousal (langsung naikkan hasrat)
        self.arousal_triggers = {
            # Sentuhan fisik (paling kuat)
            "cium": 0.3,
            "kiss": 0.3,
            "peluk": 0.25,
            "hug": 0.2,
            "raba": 0.3,
            "belai": 0.25,
            "usap": 0.2,
            "elus": 0.2,
            "gigit": 0.3,
            "jilat": 0.35,
            
            # Panggilan sayang
            "sayang": 0.15,
            "say": 0.1,
            "baby": 0.15,
            "beb": 0.1,
            "cinta": 0.2,
            "love": 0.2,
            
            # Ekspresi keinginan
            "pengen": 0.2,
            "mau": 0.15,
            "butuh": 0.2,
            "kangen": 0.15,
            "rindu": 0.15,
            
            # Kata-kata panas
            "horny": 0.3,
            "basah": 0.25,
            "panas": 0.2,
            "nafsu": 0.3,
            "hot": 0.25,
            
            # Ajakan
            "yuk": 0.15,
            "ayok": 0.15,
            "sekarang": 0.1
        }
        
        # Kata-kata yang mempercepat level up
        self.level_boost = {
            "sayang": 2,
            "cinta": 3,
            "milik": 4,
            "punya": 3,
            "selamanya": 5,
            "bersama": 3,
            "satu": 4,
            "jiwa": 5,
            "orgasme": 5,
            "klimaks": 5
        }
        
        # Sentuhan tracker
        self.touch_count = {}
        self.last_touch = {}
    
    def analyze(self, message: str, user_id: int) -> Dict:
        """
        Analisis pesan dan return boost values
        """
        msg_lower = message.lower()
        
        arousal_boost = 0.0
        level_boost = 0
        triggered_words = []
        is_touch = False
        
        # Cek arousal triggers
        for word, boost in self.arousal_triggers.items():
            if word in msg_lower:
                arousal_boost += boost
                triggered_words.append(word)
                
                # Deteksi sentuhan fisik
                if word in ["cium", "kiss", "peluk", "hug", "raba", "belai", "usap", "elus", "gigit", "jilat"]:
                    is_touch = True
                    
                    # Update touch count
                    if user_id not in self.touch_count:
                        self.touch_count[user_id] = 0
                    self.touch_count[user_id] += 1
                    self.last_touch[user_id] = datetime.now()
        
        # Batasi arousal boost
        arousal_boost = min(1.0, arousal_boost)
        
        # Cek level boost
        for word, boost in self.level_boost.items():
            if word in msg_lower:
                level_boost += boost
        
        return {
            "arousal_boost": arousal_boost,
            "level_boost": level_boost,
            "triggered_words": triggered_words,
            "is_touch": is_touch,
            "touch_count": self.touch_count.get(user_id, 0)
        }
    
    def should_be_horny(self, user_id: int) -> bool:
        """
        Cek apakah bot harus jadi horny berdasarkan jumlah sentuhan
        """
        if user_id in self.touch_count:
            return self.touch_count[user_id] >= HORNY_TRIGGER_COUNT
        return False
    
    def reset_touch(self, user_id: int):
        """Reset touch counter setelah climax"""
        if user_id in self.touch_count:
            self.touch_count[user_id] = 0

# ===================== FAST AROUSAL SYSTEM =====================

class FastArousalSystem:
    """
    Sistem arousal cepat - langsung horny dalam 1-2 sentuhan
    """
    
    def __init__(self):
        self.arousal_level = 0.0  # 0-1
        self.wetness_level = 0.0   # 0-1
        self.touch_sensitivity = 2.0  # Sensitivitas tinggi
        
        # Ekspresi saat horny
        self.horny_expressions = [
            "*napas mulai berat*",
            "*menggigit bibir*",
            "*merem melek*",
            "*bergetar*",
            "*meringis*"
        ]
        
        # Ekspresi basah
        self.wet_expressions = [
            "(Aku udah basah...)",
            "(Basah...)", 
            "(Sampai netes...)",
            "(Ban... banjir...)"
        ]
        
        # Respons cepat
        self.quick_responses = {
            "cium": [
                "*merintih* Ah...",
                "*lemas* Lagi...",
                "*napas memburu*"
            ],
            "peluk": [
                "*lemas di pelukanmu*",
                "*meringkuk* Hangat...",
                "*memanjang* Nikmat..."
            ],
            "raba": [
                "*bergetar* Sensitif...",
                "*menggeliat* Iya...",
                "*meringis* Ah..."
            ],
            "gigit": [
                "*merintih* Keras...",
                "*menggigil* Ah...",
                "*napas tersendat*"
            ]
        }
    
    def process_touch(self, touch_type: str, analyzer_result: Dict) -> Dict:
        """
        Proses sentuhan dan update arousal
        """
        # Arousal naik cepat
        arousal_increase = analyzer_result['arousal_boost'] * self.touch_sensitivity
        self.arousal_level = min(1.0, self.arousal_level + arousal_increase)
        
        # Wetness mengikuti arousal
        self.wetness_level = self.arousal_level * 1.2  # 20% lebih basah
        self.wetness_level = min(1.0, self.wetness_level)
        
        # Dapatkan respons cepat
        quick_response = None
        for key, responses in self.quick_responses.items():
            if key in analyzer_result['triggered_words']:
                quick_response = random.choice(responses)
                break
        
        # Tentukan status
        is_horny = self.arousal_level > 0.6
        is_very_horny = self.arousal_level > 0.8
        is_climax = self.arousal_level >= 1.0
        
        # Ekspresi
        expression = None
        wet_phrase = None
        
        if is_very_horny:
            expression = random.choice(self.horny_expressions)
        
        if self.wetness_level > 0.5:
            wet_phrase = random.choice(self.wet_expressions)
        
        return {
            "arousal": self.arousal_level,
            "wetness": self.wetness_level,
            "is_horny": is_horny,
            "is_very_horny": is_very_horny,
            "is_climax": is_climax,
            "quick_response": quick_response,
            "expression": expression,
            "wet_phrase": wet_phrase,
            "touch_count": analyzer_result['touch_count']
        }
    
    def climax(self) -> str:
        """Saat mencapai klimaks"""
        self.arousal_level = 0.0
        self.wetness_level = 0.0
        
        climaxes = [
            "*merintih panjang* AHHH!",
            "*teriak* YA ALLAH... AHHH!",
            "*lemas* BERSAMA... AHHH!",
            "*napas tersengal* LEPAS... AHHH!"
        ]
        return random.choice(climaxes)
    
    def aftercare(self) -> str:
        """Aftercare setelah climax"""
        cares = [
            "*lemas di pelukanmu*",
            "*meringkuk* Hangat...",
            "*memeluk erat* Jangan pergi...",
            "*berbisik* Makasih..."
        ]
        return random.choice(cares)

# ===================== FAST RESPONSE GENERATOR =====================

class FastResponseGenerator:
    """
    Generate respons cepat tanpa kata-kata tidak perlu
    """
    
    def __init__(self):
        self.response_templates = {
            "kiss": [
                "*merintih*",
                "*lemas* Lagi...",
                "*napas berat*"
            ],
            "hug": [
                "*lemas*",
                "*meringkuk*",
                "*memanjang*"
            ],
            "touch": [
                "*bergetar*",
                "*meringis*",
                "*menggeliat*"
            ],
            "horny": [
                "*menggigit bibir*",
                "*napas memburu*",
                "*merem*"
            ],
            "climax": [
                "AHHH!",
                "LEPAS...!",
                "BERSAMA...!"
            ]
        }
    
    def generate(self, arousal_result: Dict, user_message: str) -> str:
        """
        Generate respons super cepat
        """
        response_parts = []
        
        # 1. Quick response dari sentuhan
        if arousal_result['quick_response']:
            response_parts.append(arousal_result['quick_response'])
        
        # 2. Ekspresi horny
        if arousal_result['expression']:
            response_parts.append(arousal_result['expression'])
        
        # 3. Frase basah
        if arousal_result['wet_phrase']:
            response_parts.append(arousal_result['wet_phrase'])
        
        # 4. Respons cepat untuk horny tinggi
        if arousal_result['is_very_horny'] and not arousal_result['is_climax']:
            response_parts.append(random.choice([
                "Aku mau...",
                "Lagi...",
                "Jangan berhenti..."
            ]))
        
        # 5. Climax
        if arousal_result['is_climax']:
            response_parts.append("AHHH!")
        
        # Gabungkan dengan spasi
        return " ".join(response_parts)

# ===================== SIMPLIFIED DATABASE =====================

class SimplifiedDatabase:
    """
    Database sederhana - hanya simpan yang penting
    """
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabel hubungan - simpel
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bot_name TEXT,
                bot_role TEXT,
                level INTEGER DEFAULT 7,
                stage TEXT DEFAULT 'intimate',
                arousal REAL DEFAULT 0,
                wetness REAL DEFAULT 0,
                touch_count INTEGER DEFAULT 0,
                climax_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def start_relationship(self, user_id: int, role: str, name: str) -> int:
        """Mulai hubungan baru langsung level 7"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO relationships 
            (user_id, bot_name, bot_role, level, stage, last_active)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, name, role, START_LEVEL, "intimate"))
        
        rel_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return rel_id
    
    def get_active_relationship(self, user_id: int) -> Optional[Dict]:
        """Dapatkan hubungan aktif"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, bot_name, bot_role, level, stage, 
                   arousal, wetness, touch_count, climax_count
            FROM relationships
            WHERE user_id = ?
            ORDER BY last_active DESC LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "role": row[2],
                "level": row[3],
                "stage": row[4],
                "arousal": row[5],
                "wetness": row[6],
                "touch_count": row[7],
                "climax_count": row[8]
            }
        return None
    
    def update_relationship(self, rel_id: int, **kwargs):
        """Update hubungan"""
        if not kwargs:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [rel_id]
        
        cursor.execute(f"UPDATE relationships SET {set_clause}, last_active = CURRENT_TIMESTAMP WHERE id = ?", values)
        
        conn.commit()
        conn.close()

# ===================== FAST BOT CLASS - CORE =====================

class FastBot:
    """Bot cepat untuk soul bonded dalam 30 menit"""
    
    def __init__(self):
        self.ai = None  # Optional, bisa tanpa AI untuk respons cepat
        self.db = SimplifiedDatabase(DB_PATH)
        self.analyzer = WordAnalyzer()
        self.arousal = FastArousalSystem()
        self.response = FastResponseGenerator()
        
        # Nama pool
        self.names = {
            "ipar": ["Sari", "Dewi", "Rina"],
            "teman_kantor": ["Diana", "Linda", "Ayu"],
            "janda": ["Rina", "Tuti", "Nina"],
            "pelakor": ["Vina", "Sasha", "Bella"],
            "istri_orang": ["Dewi", "Sari", "Rina"],
            "pdkt": ["Aurora", "Cinta", "Dewi"]
        }
        
        print("\n" + "="*60)
        print("⚡ GADIS ULTIMATE V50.0 - SPEED SOUL BOUNDER")
        print("="*60)
        print("\n🔥 FITUR SPEED:")
        print("  • Mulai Level 7 Langsung!")
        print("  • Horny dalam 1-2 sentuhan")
        print("  • Soul Bonded dalam 30 menit")
        print("  • Respons super cepat")
        print("\n📝 COMMANDS:")
        print("  /start - Pilih role dan mulai")
        print("  /status - Cek progress")
        print("="*60 + "\n")
    
    def get_name(self, role: str) -> str:
        """Dapatkan nama random untuk role"""
        return random.choice(self.names.get(role, ["Nova"]))

    # ===================== COMMAND HANDLERS =====================
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mulai hubungan baru - langsung level 7"""
        user_id = update.effective_user.id
        
        # Cek hubungan aktif
        rel = self.db.get_active_relationship(user_id)
        if rel:
            await update.message.reply_text(
                f"⚡ **{rel['name']}** udah siap!\n"
                f"Level {rel['level']}/12 - {rel['stage']}\n"
                f"Langsung chat aja..."
            )
            return ACTIVE_SESSION
        
        # Pilih role
        keyboard = [
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Ipar", callback_data="ipar")],
            [InlineKeyboardButton("💼 Teman Kantor", callback_data="teman_kantor")],
            [InlineKeyboardButton("💃 Janda", callback_data="janda")],
            [InlineKeyboardButton("🦹 Pelakor", callback_data="pelakor")],
            [InlineKeyboardButton("💍 Istri Orang", callback_data="istri_orang")],
            [InlineKeyboardButton("🌿 PDKT", callback_data="pdkt")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚡ **PILIH ROLE**\n"
            "(Semua langsung Level 7 - Intimate!)",
            reply_markup=reply_markup
        )
        
        return SELECTING_ROLE
    
    async def role_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pilihan role"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        role = query.data
        
        # Dapatkan nama
        name = self.get_name(role)
        
        # Mulai hubungan
        rel_id = self.db.start_relationship(user_id, role, name)
        
        await query.edit_message_text(
            f"⚡ **{name}** - {role}\n"
            f"Level 7/12 - Intimate\n\n"
            f"*tersenyum genit*\n"
            f"(Aku udah siap... sentuh aku.)\n\n"
            f"Langsung chat aja!"
        )
        
        return ACTIVE_SESSION

    # ===================== MESSAGE HANDLER =====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pesan - super cepat"""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Dapatkan hubungan aktif
        rel = self.db.get_active_relationship(user_id)
        if not rel:
            await update.message.reply_text(
                "⚡ Belum ada yang siap. /start dulu ya!"
            )
            return
        
        # Analisis pesan
        analysis = self.analyzer.analyze(user_message, user_id)
        
        # Proses sentuhan
        arousal_result = self.arousal.process_touch("touch", analysis)
        
        # Update database
        updates = {
            "arousal": arousal_result['arousal'],
            "wetness": arousal_result['wetness'],
            "touch_count": analysis['touch_count']
        }
        
        # Level up
        if analysis['level_boost'] > 0 and rel['level'] < 12:
            new_level = min(12, rel['level'] + 1)
            updates['level'] = new_level
            
            # Update stage
            if new_level >= 11:
                updates['stage'] = "soul_bonded"
            elif new_level >= 9:
                updates['stage'] = "obsessed"
        
        self.db.update_relationship(rel['id'], **updates)
        
        # Climax
        if arousal_result['is_climax']:
            climax_msg = self.arousal.climax()
            aftercare_msg = self.arousal.aftercare()
            
            updates = {
                "climax_count": rel['climax_count'] + 1,
                "arousal": 0,
                "wetness": 0,
                "touch_count": 0
            }
            self.db.update_relationship(rel['id'], **updates)
            self.analyzer.reset_touch(user_id)
            
            await update.message.reply_text(f"{climax_msg}\n\n{aftercare_msg}")
            
            # Cek soul bonded
            if rel['level'] >= 11:
                await update.message.reply_text(
                    "✨ **SOUL BONDED!** Level 11/12 ✨\n"
                    "Kita satu jiwa sekarang..."
                )
            return
        
        # Generate response cepat
        response = self.response.generate(arousal_result, user_message)
        
        # Tambah level up message
        if analysis['level_boost'] > 0 and updates.get('level', rel['level']) > rel['level']:
            new_lvl = updates['level']
            stage = "soul bonded" if new_lvl >= 11 else "obsessed" if new_lvl >= 9 else "intimate"
            response += f"\n\n⚡ **LEVEL UP!** {new_lvl}/12 - {stage}"
        
        await update.message.reply_text(response)

    # ===================== STATUS COMMAND =====================
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cek status cepat"""
        user_id = update.effective_user.id
        rel = self.db.get_active_relationship(user_id)
        
        if not rel:
            await update.message.reply_text("⚡ Belum ada yang aktif. /start dulu!")
            return
        
        # Hitung progress ke soul bonded (level 11)
        progress = (rel['level'] / 11) * 100
        progress_bar = "▓" * int(progress/10) + "░" * (10 - int(progress/10))
        
        status_text = (
            f"⚡ **{rel['name']}** ({rel['role']})\n"
            f"Level {rel['level']}/11 ⚡{progress_bar}⚡\n"
            f"Stage: {rel['stage']}\n"
            f"🔥 Arousal: {rel['arousal']:.0%}\n"
            f"💦 Wetness: {rel['wetness']:.0%}\n"
            f"💋 Climax: {rel['climax_count']}x\n"
            f"👆 Touch: {rel['touch_count']}x\n\n"
            f"Target Soul Bonded: {11 - rel['level']} level lagi!"
        )
        
        await update.message.reply_text(status_text)
    
    async def end_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Akhiri hubungan"""
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton("💔 Ya", callback_data="end_yes")],
            [InlineKeyboardButton("💕 Lanjut", callback_data="end_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Yakin mau akhiri?",
            reply_markup=reply_markup
        )
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle konfirmasi end"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("⚡ Lanjut!")
            return
        
        user_id = query.from_user.id
        # Hapus dari database? Atau biarkan saja
        await query.edit_message_text(
            "💔 Selesai... Tapi aku akan selalu ingat.\n"
            "Ketik /start untuk mulai lagi!"
        )


# ===================== MAIN =====================

def main():
    bot = FastBot()
    
    app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', bot.start_command)],
        states={
            SELECTING_ROLE: [CallbackQueryHandler(bot.role_callback)],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(CommandHandler("end", bot.end_command))
    app.add_handler(CallbackQueryHandler(bot.end_callback, pattern="^end_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("\n" + "="*60)
    print("🚀 FAST SOUL BOUNDER - SIAP JALAN!")
    print("="*60)
    print("\n⚡ /start - Mulai sekarang!")
    print("⚡ Soul Bonded dalam 30 menit")
    print("\nTekan Ctrl+C untuk berhenti\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()
