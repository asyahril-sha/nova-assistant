# force_migrate.py
import sqlite3
import os

DB_PATH = "gadis_v59.db"

if not os.path.exists(DB_PATH):
    print(f"Database {DB_PATH} tidak ditemukan!")
    exit(1)

print(f"📊 Membuka database {DB_PATH}...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Cek kolom yang ada
cursor.execute("PRAGMA table_info(relationships)")
columns = [col[1] for col in cursor.fetchall()]
print("Kolom yang ada saat ini:", columns)

# Kolom yang harus ditambahkan
required_columns = {
    "current_clothing": "TEXT DEFAULT 'pakaian biasa'",
    "last_clothing_change": "TIMESTAMP",
    "hair_style": "TEXT",
    "height": "INTEGER",
    "weight": "INTEGER",
    "breast_size": "TEXT",
    "hijab": "BOOLEAN DEFAULT 0",
    "most_sensitive_area": "TEXT"
}

# Tambahkan kolom yang hilang
for col_name, col_type in required_columns.items():
    if col_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE relationships ADD COLUMN {col_name} {col_type}")
            print(f"✅ Kolom '{col_name}' berhasil ditambahkan")
        except Exception as e:
            print(f"❌ Gagal menambahkan '{col_name}': {e}")
    else:
        print(f"⏭️ Kolom '{col_name}' sudah ada")

conn.commit()
conn.close()
print("\n✅ Migrasi selesai!")
