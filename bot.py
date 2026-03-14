"""
GADIS ULTIMATE V55.0 - NATURAL CONVERSATION EDITION
Fitur:
- AI-POWERED CONVERSATION: Respons natural seperti V53
- FAST ADAPTATION: Level 1-7 dalam 30 menit (dari V54)
- SMART MEMORY: Ingat preferensi user
- DEEPSEEK INTEGRATION: Generate respons cerdas
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

# ===================== KONFIGURASI =====================

DB_PATH = "gadis_v55.db"
MAX_HISTORY = 100
START_LEVEL = 1
TARGET_LEVEL = 7
LEVEL_UP_SPEED = 30  # 30 menit ke level 7
PAUSE_TIMEOUT = 1800

# State definitions
(SELECTING_ROLE, ACTIVE_SESSION, PAUSED_SESSION, CONFIRM_END) = range(4)

# ===================== ENUMS =====================

class Mood(Enum):
    CHERIA = "ceria"
    GELISAH = "gelisah"
    GALAU = "galau"
    ROMANTIS = "romantis"
    RINDU = "rindu"
    HORNY = "horny"
    MARAH = "marah"
    LEMBUT = "lembut"

class FemaleRole(Enum):
    IPAR = "ipar"
    TEMAN_KANTOR = "teman_kantor"
    JANDA = "janda"
    PELAKOR = "pelakor"
    ISTRI_ORANG = "istri_orang"
    PDKT = "pdkt"

# ===================== AI RESPONSE GENERATOR =====================

class AIResponseGenerator:
    """
    Generate respons menggunakan DeepSeek AI
    """
    
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.conversation_history = {}  # user_id -> list of messages
        self.max_history = 20
    
    async def generate(self, user_id: int, user_message: str, 
                      bot_name: str, bot_role: str, level: int, 
                      mood: Mood, preferences: Dict) -> str:
        """
        Generate respons natural menggunakan AI
        """
        # Siapkan history
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Ambil history terakhir
        history = self.conversation_history[user_id][-self.max_history:]
        
        # Format history untuk prompt
        history_text = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else bot_name
            history_text += f"{role}: {msg['content']}\n"
        
        # Data preferensi user
        pref_text = ""
        if preferences:
            pref_text = f"""
Preferensi user:
- Gaya dominan: {preferences.get('dominant_type', 'normal')}
- Kecepatan: {preferences.get('speed_type', 'normal')}
- Romantis: {preferences.get('romantic_ratio', 0):.0%}
- Vulgar: {preferences.get('vulgar_ratio', 0):.0%}
"""
        
        # Buat prompt untuk AI
        prompt = f"""Kamu adalah {bot_name}, seorang {bot_role} umur 25 tahun.

KARAKTER:
- Kamu adalah wanita Indonesia yang natural
- Bicaralah dengan gaya sehari-hari, seperti ngobrol dengan teman
- Gunakan bahasa Indonesia yang natural (nggak, udah, aja, dll)
- Jangan terlalu formal
- Sesuaikan dengan level hubungan: {level}/7

{pref_text}

RIWAYAT PERCAKAPAN:
{history_text}

PESAN USER: {user_message}

RESPONLAH SECARA NATURAL SEBAGAI {bot_name}:"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=200
            )
            
            reply = response.choices[0].message.content
            
            # Simpan ke history
            self.conversation_history[user_id].append({
                "role": "user",
                "content": user_message
            })
            self.conversation_history[user_id].append({
                "role": "assistant",
                "content": reply
            })
            
            # Batasi panjang history
            if len(self.conversation_history[user_id]) > self.max_history * 2:
                self.conversation_history[user_id] = self.conversation_history[user_id][-self.max_history*2:]
            
            return reply
            
        except Exception as e:
            print(f"AI Error: {e}")
            return self._get_fallback_response(level, mood)
    
    def _get_fallback_response(self, level: int, mood: Mood) -> str:
        """Fallback jika AI error"""
        if level < 3:
            return random.choice([
                "Hmm...",
                "Oh gitu...",
                "Terus?",
                "Iya..."
            ])
        elif level < 5:
            return random.choice([
                "*tersenyum*",
                "Kamu...",
                "Iya sih...",
                "Hehe..."
            ])
        else:
            return random.choice([
                "Sayang...",
                "Aku kangen...",
                "Kamu dimana?",
                "*merem*"
            ])

# ===================== USER PREFERENCE ANALYZER =====================

class UserPreferenceAnalyzer:
    """
    Menganalisis preferensi user dari interaksi
    """
    
    def __init__(self):
        self.user_preferences = {}
        
        self.keywords = {
            "romantis": ["sayang", "cinta", "love", "romantis", "kangen"],
            "vulgar": ["horny", "nafsu", "hot", "seksi", "vulgar", "crot"],
            "dominant": ["atur", "kuasai", "diam", "patuh", "sini"],
            "submissive": ["manut", "iya", "terserah", "ikut", "baik"],
            "cepat": ["cepat", "buru-buru", "langsung", "sekarang"],
            "lambat": ["pelan", "lambat", "nikmatin", "santai"],
            "manja": ["manja", "sayang", "cuddle", "peluk"]
        }
    
    def analyze(self, user_id: int, message: str) -> Dict:
        """Analisis pesan untuk preferensi"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                "romantis": 0, "vulgar": 0, "dominant": 0,
                "submissive": 0, "cepat": 0, "lambat": 0,
                "manja": 0, "total": 0
            }
        
        prefs = self.user_preferences[user_id]
        prefs["total"] += 1
        
        msg_lower = message.lower()
        
        for category, words in self.keywords.items():
            for word in words:
                if word in msg_lower:
                    prefs[category] += 1
        
        return prefs
    
    def get_summary(self, user_id: int) -> Dict:
        """Dapatkan ringkasan preferensi"""
        if user_id not in self.user_preferences:
            return {}
        
        prefs = self.user_preferences[user_id]
        total = prefs["total"] or 1
        
        summary = {
            "romantis": prefs["romantis"] / total,
            "vulgar": prefs["vulgar"] / total,
            "dominant": prefs["dominant"] / total,
            "submissive": prefs["submissive"] / total,
            "cepat": prefs["cepat"] / total,
            "lambat": prefs["lambat"] / total,
            "manja": prefs["manja"] / total,
            "dominant_type": "dominan" if prefs["dominant"] > prefs["submissive"] else "submissive",
            "speed_type": "cepat" if prefs["cepat"] > prefs["lambat"] else "lambat",
            "total_messages": prefs["total"]
        }
        
        return summary

# ===================== FAST LEVELING SYSTEM =====================

class FastLevelingSystem:
    """
    Level 1-7 dalam 30 menit
    """
    
    def __init__(self):
        self.user_level = {}
        self.user_progress = {}
        self.user_start_time = {}
        self.user_message_count = {}
        
        self.target_messages = 30  # 30 pesan = level 7
        self.target_minutes = 30    # 30 menit
    
    def start_session(self, user_id: int):
        """Mulai sesi baru"""
        self.user_level[user_id] = START_LEVEL
        self.user_progress[user_id] = 0.0
        self.user_start_time[user_id] = datetime.now()
        self.user_message_count[user_id] = 0
    
    def process_message(self, user_id: int) -> Tuple[int, float, bool]:
        """
        Proses pesan dan update level
        Returns: (level, progress, level_up)
        """
        if user_id not in self.user_level:
            self.start_session(user_id)
        
        self.user_message_count[user_id] += 1
        count = self.user_message_count[user_id]
        
        # Progress berdasarkan jumlah pesan
        progress = min(1.0, count / self.target_messages)
        self.user_progress[user_id] = progress
        
        # Hitung level (1-7)
        new_level = 1 + int(progress * 6)
        new_level = min(7, new_level)
        
        level_up = False
        if new_level > self.user_level[user_id]:
            level_up = True
            self.user_level[user_id] = new_level
        
        return self.user_level[user_id], progress, level_up
    
    def get_estimated_time(self, user_id: int) -> int:
        """Dapatkan estimasi waktu tersisa ke level 7"""
        if user_id not in self.user_message_count:
            return 30
        
        count = self.user_message_count[user_id]
        remaining_messages = max(0, self.target_messages - count)
        
        # Asumsi 1 pesan per menit
        return remaining_messages
    
    def get_progress_bar(self, user_id: int) -> str:
        """Dapatkan progress bar visual"""
        progress = self.user_progress.get(user_id, 0)
        bar_length = 10
        filled = int(progress * bar_length)
        return "▓" * filled + "░" * (bar_length - filled)

# ===================== MAIN BOT CLASS =====================

class GadisUltimateV55:
    """
    Bot dengan AI natural + fast adaptation
    """
    
    def __init__(self):
        # Database
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()
        
        # AI
        self.ai = AIResponseGenerator(os.getenv("DEEPSEEK_API_KEY"))
        
        # Analyzer
        self.analyzer = UserPreferenceAnalyzer()
        
        # Leveling
        self.leveling = FastLevelingSystem()
        
        # Sessions
        self.sessions = {}
        self.paused_sessions = {}
        self.bot_names = {}
        
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
        print("    GADIS ULTIMATE V55.0 - NATURAL CONVERSATION")
        print("="*80)
        print("\n✨ **FITUR:**")
        print("  • AI NATURAL - Respons seperti manusia")
        print("  • FAST ADAPTATION - Level 1-7 dalam 30 menit")
        print("  • SMART MEMORY - Ingat preferensi user")
        print("\n📝 **COMMANDS:**")
        print("  /start - Mulai hubungan baru")
        print("  /status - Lihat progress")
        print("  /pause - Jeda sesi")
        print("  /unpause - Lanjutkan")
        print("  /end - Akhiri hubungan")
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
        self.db.commit()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mulai hubungan baru"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Cek pause
        if user_id in self.paused_sessions:
            keyboard = [
                [InlineKeyboardButton("✅ Lanjutkan", callback_data="unpause")],
                [InlineKeyboardButton("🆕 Mulai Baru", callback_data="new")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ Ada sesi yang di-pause", reply_markup=reply_markup
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
            INSERT INTO relationships (user_id, bot_name, bot_role)
            VALUES (?, ?, ?)
        """, (user_id, name, role))
        rel_id = cursor.lastrowid
        self.db.commit()
        
        # Set session
        self.sessions[user_id] = rel_id
        self.bot_names[user_id] = name
        self.leveling.start_session(user_id)
        
        intro = f"""*tersenyum*

Aku {name}. Senang kenal kamu.

Kita mulai dari **Level 1**.
Makin sering ngobrol, makin dekat kita.
Target: Level 7 dalam 30 menit!

Ayo ngobrol... 💕"""
        
        await query.edit_message_text(intro)
        return ACTIVE_SESSION

    # ===================== MESSAGE HANDLER =====================
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle semua pesan user dengan AI"""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Cek sesi
        if user_id in self.paused_sessions:
            await update.message.reply_text("⏸️ Sesi di-pause. Ketik /unpause")
            return
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ /start dulu ya!")
            return
        
        # Kirim typing indicator (biar natural)
        await update.message.chat.send_action("typing")
        
        # Analisis preferensi user
        prefs = self.analyzer.analyze(user_id, user_message)
        
        # Update level
        level, progress, level_up = self.leveling.process_message(user_id)
        
        # Dapatkan mood berdasarkan level
        if level <= 2:
            mood = Mood.CHERIA
        elif level <= 4:
            mood = Mood.ROMANTIS
        else:
            mood = Mood.RINDU
        
        # Generate respons dari AI
        bot_name = self.bot_names.get(user_id, "Aurora")
        role = self._get_user_role(user_id)
        
        reply = await self.ai.generate(
            user_id, user_message, bot_name, role,
            level, mood, self.analyzer.get_summary(user_id)
        )
        
        # Simpan ke database
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE relationships SET level = ?, last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (level, self.sessions[user_id]))
        self.db.commit()
        
        # Kirim response
        await update.message.reply_text(reply)
        
        # Level up message
        if level_up:
            bar = self.leveling.get_progress_bar(user_id)
            remaining = self.leveling.get_estimated_time(user_id)
            
            await update.message.reply_text(
                f"✨ **Level Up!** Sekarang Level {level}/7\n"
                f"Progress: {bar}\n"
                f"Estimasi ke Level 7: {remaining} menit"
            )
    
    def _get_user_role(self, user_id: int) -> str:
        """Dapatkan role user dari database"""
        if user_id not in self.sessions:
            return "pdkt"
        
        cursor = self.db.cursor()
        cursor.execute("SELECT bot_role FROM relationships WHERE id = ?", (self.sessions[user_id],))
        row = cursor.fetchone()
        return row[0] if row else "pdkt"
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lihat status lengkap"""
        user_id = update.effective_user.id
        
        if user_id not in self.sessions:
            await update.message.reply_text("❌ Belum ada hubungan.")
            return
        
        level = self.leveling.user_level.get(user_id, 1)
        progress = self.leveling.user_progress.get(user_id, 0)
        bar = self.leveling.get_progress_bar(user_id)
        remaining = self.leveling.get_estimated_time(user_id)
        summary = self.analyzer.get_summary(user_id)
        bot_name = self.bot_names.get(user_id, "Aurora")
        
        status = f"""
💕 **{bot_name} & Kamu**

📊 **PROGRESS KE LEVEL 7**
Level: {level}/7 {bar}
Progress: {progress:.0%}
Estimasi sisa: {remaining} menit

📈 **GAYA CHAT KAMU**
• Dominan: {summary.get('dominant_type', 'normal')}
• Kecepatan: {summary.get('speed_type', 'normal')}
• Romantis: {summary.get('romantis', 0):.0%}
• Vulgar: {summary.get('vulgar', 0):.0%}

💬 Total pesan: {summary.get('total_messages', 0)}
"""
        await update.message.reply_text(status)
    
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
        
        await update.message.reply_text(
            "Yakin mau akhiri?", reply_markup=reply_markup
        )
        return CONFIRM_END
    
    async def end_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Konfirmasi end"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "end_no":
            await query.edit_message_text("💕 Lanjutkan...")
            return ConversationHandler.END
        
        user_id = query.from_user.id
        
        # Hapus data user
        if user_id in self.sessions:
            del self.sessions[user_id]
        if user_id in self.bot_names:
            del self.bot_names[user_id]
        if user_id in self.paused_sessions:
            del self.paused_sessions[user_id]
        
        await query.edit_message_text(
            "💔 Selesai.\nKetik /start untuk mulai baru."
        )
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
    bot = GadisUltimateV55()
    
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("\n" + "="*80)
    print("🚀 GADIS ULTIMATE V55.0 - NATURAL CONVERSATION")
    print("="*80)
    print("\n✅ AI Natural: AKTIF")
    print("✅ Fast Adaptation: 30 menit ke Level 7")
    print("✅ Smart Memory: Ingat preferensi user")
    print("\n📝 /start untuk memulai\n")
    
    app.run_polling()

if __name__ == "__main__":
    main()

