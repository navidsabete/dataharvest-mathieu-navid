import csv
import json
import sqlite3
from pathlib import Path

class Store:
   
   BACKENDS = ('csv', 'sqlite', 'json')

   def __init__(self, backend: str, path: str):
     if backend not in self.BACKENDS:
        raise ValueError(f'Backend inconnu: {backend}')
     self.backend = backend
     self.path = Path(path)
     self.path.parent.mkdir(parents=True, exist_ok=True)
   
   def save(self, items: list[dict]) -> int:
     """Persiste les items. Retourne le nombre d'items insérés (hors doublons)."""

     if self.backend == "csv":
            return self.save_csv(items)
     if self.backend == "sqlite":
         return self.save_sqlite(items) 
     if self.backend == "json":
         return self.save_json(items)

   def save_csv(self, items):
        if not items:
            return 0
        file_exists = self.path.exists()

        with open(self.path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=items[0].keys())
            if not file_exists:
                writer.writeheader()
            writer.writerows(items)
        return len(items)

   def save_sqlite(self, items):
        if not items:
            return 0

        inserted = 0

        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()
            columns = ", ".join(items[0].keys())
            placeholders = ", ".join(["?"] * len(items[0]))

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {columns},
                    UNIQUE(url)
                )
                """
            )

            for item in items:
                try:
                    cursor.execute(f"""INSERT OR IGNORE INTO items({columns})
                        VALUES ({placeholders})""", tuple(item.values()))

                    if cursor.rowcount:
                        inserted += 1

                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        return inserted

   def save_json(self, items):
        existing = []

        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.extend(items)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        return len(items)
  

   def count(self) -> int:
     """Retourne le nombre total d'items dans le store."""  

     if self.backend == "json":
        if not self.path.exists():
            return 0
            
        with open(self.path, encoding="utf-8") as f:
            return len(json.load(f))

     if self.backend == "csv":
        if not self.path.exists():
            return 0

        with open(self.path, encoding="utf-8") as f:
            return sum(1 for _ in f) - 1

     if self.backend == "sqlite":
        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM items")
            return cursor.fetchone()[0]

   def export_to(self, other_backend: str, path: str) -> int:
     """Exporte tous les items vers un autre backend. Retourne le nb exporté."""

     items = self.load_all()
     target = Store(other_backend, path)

     return target.save(items)

   def load_all(self):
        if self.backend == "json":
            if not self.path.exists():
                return []

            with open(self.path, encoding="utf-8") as f:
                return json.load(f)

        if self.backend == "csv":
            if not self.path.exists():
                return []

            with open(self.path, encoding="utf-8") as f:
                return list(csv.DictReader(f))

        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM items")
                rows = cursor.fetchall()
                columns = [
                    description[0]
                    for description in cursor.description
                ]
                return [dict(zip(columns, row))for row in rows
                ]
