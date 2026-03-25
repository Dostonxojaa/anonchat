import sqlite3
from datetime import datetime, timedelta

class database:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._migrate_database()

    def _create_tables(self):
        """Создание таблиц с актуальной структурой"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                status INTEGER DEFAULT 0,
                rid INTEGER DEFAULT 0,
                interests TEXT DEFAULT '',
                blocked BOOLEAN DEFAULT 0,
                blocked_until TEXT DEFAULT NULL,
                search_started TEXT DEFAULT NULL
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_links (
                user_id INTEGER,
                message_id INTEGER,
                rival_message_id INTEGER,
                PRIMARY KEY(user_id, message_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                content TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица для рейтингов пользователей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ratings (
                user_id INTEGER PRIMARY KEY,
                positive INTEGER DEFAULT 0,
                negative INTEGER DEFAULT 0
            )
        """)
        
        # Таблица для хранения последнего собеседника для оценки/жалоб
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_rivals (
                user_id INTEGER PRIMARY KEY,
                rival_id INTEGER
            )
        """)
        
        self.conn.commit()

    def _migrate_database(self):
        """Миграции для существующих баз данных"""
        try:
            self.cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in self.cursor.fetchall()]
            
            if 'interests' not in columns:
                self.cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN interests TEXT DEFAULT ''
                """)
                self.conn.commit()
            if 'blocked' not in columns:
                self.cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN blocked BOOLEAN DEFAULT 0
                """)
                self.conn.commit()
            if 'blocked_until' not in columns:
                self.cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN blocked_until TEXT DEFAULT NULL
                """)
                self.conn.commit()
            if 'search_started' not in columns:
                self.cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN search_started TEXT DEFAULT NULL
                """)
                self.conn.commit()
        except sqlite3.Error as e:
            print(f"Migration error: {e}")

        # Создать таблицы рейтингов и last_rivals, если их нет (для обновления старых баз)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_ratings (
                user_id INTEGER PRIMARY KEY,
                positive INTEGER DEFAULT 0,
                negative INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_rivals (
                user_id INTEGER PRIMARY KEY,
                rival_id INTEGER
            )
        """)
        self.conn.commit()

    def get_user_cursor(self, user_id: int) -> dict:
        """Получение информации о пользователе"""
        try:
            self.cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            result = self.cursor.fetchone()
            return dict(result) if result else None
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                self._migrate_database()
                return self.get_user_cursor(user_id)
            raise

    def new_user(self, user_id: int):
        """Добавляет нового пользователя"""
        self.cursor.execute(
            "INSERT OR IGNORE INTO users (id) VALUES (?)",
            (user_id,)
        )
        self.conn.commit()

    def search(self, user_id: int):
        """Поиск подходящего собеседника с учетом рейтинга и интересов"""
        current_user = self.get_user_cursor(user_id)
        if not current_user:
            return None

        now_str = datetime.now().isoformat()
        self.cursor.execute(
            "UPDATE users SET status = 1, rid = 0, search_started = ? WHERE id = ?",
            (now_str, user_id)
        )
        self.conn.commit()

        user_interests = set(current_user['interests'].split(',')) if current_user['interests'] else set()

        self.cursor.execute(
            "SELECT id, interests FROM users WHERE status = 1 AND id != ?",
            (user_id,)
        )
        candidates = []
        for candidate in self.cursor.fetchall():
            c_id, c_interests = candidate['id'], candidate['interests']
            candidate_interests = set(c_interests.split(',')) if c_interests else set()

            # Получаем рейтинг кандидата
            c_rating = self.get_user_rating(c_id)
            c_pos = c_rating['positive']
            c_neg = c_rating['negative']

            # Фильтр по интересам
            if not user_interests or user_interests & candidate_interests:
                candidates.append({
                    "id": c_id,
                    "interests": candidate_interests,
                    "positive": c_pos,
                    "negative": c_neg
                })

        # Сортируем кандидатов с учетом рейтинга и пересечения интересов:
        # 1) Чем больше совпадений интересов - выше
        # 2) Пользователи с >=5 негативными рейтингами идут в конец
        # 3) Пользователи с >=5 положительными рейтингами идут в начало
        def sort_key(c):
            interest_score = len(user_interests & c['interests'])
            rating_score = 0
            if c['negative'] >= 5:
                rating_score -= 1000  # очень низкий приоритет
            if c['positive'] >= 5:
                rating_score += 1000  # очень высокий приоритет
            return (rating_score, interest_score)

        candidates.sort(key=sort_key, reverse=True)

        return candidates[0] if candidates else None

    def start_chat(self, user_id: int, rival_id: int):
        """Начинает чат между двумя пользователями и сохраняет последний собеседник"""
        self.cursor.executemany(
            "UPDATE users SET status = 2, rid = ?, search_started = NULL WHERE id = ?",
            [(rival_id, user_id), (user_id, rival_id)]
        )
        # Сохраняем в last_rivals для оценки и жалоб после окончания
        self.cursor.execute("INSERT OR REPLACE INTO last_rivals (user_id, rival_id) VALUES (?, ?)", (user_id, rival_id))
        self.cursor.execute("INSERT OR REPLACE INTO last_rivals (user_id, rival_id) VALUES (?, ?)", (rival_id, user_id))
        self.conn.commit()

    def stop_chat(self, user_id: int, rival_id: int):
        """Завершает чат между пользователями"""
        self.cursor.executemany(
            "UPDATE users SET status = 0, rid = 0, search_started = NULL WHERE id = ?",
            [(user_id,), (rival_id,)]
        )
        self.conn.commit()

    def stop_search(self, user_id: int):
        """Останавливает поиск собеседника"""
        self.cursor.execute(
            "UPDATE users SET status = 0, rid = 0, search_started = NULL WHERE id = ?",
            (user_id,)
        )
        self.conn.commit()

    def save_message_link(self, user_id: int, message_id: int, rival_message_id: int):
        """Сохраняет связь между сообщениями"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO message_links VALUES (?, ?, ?)",
            (user_id, message_id, rival_message_id)
        )
        self.conn.commit()

    def get_rival_message_id(self, user_id: int, message_id: int) -> int:
        """Получает ID связанного сообщения"""
        self.cursor.execute(
            "SELECT rival_message_id FROM message_links WHERE user_id = ? AND message_id = ?",
            (user_id, message_id)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def add_interest(self, user_id: int, interest: str):
        """Добавляет интерес пользователю"""
        interests = self.get_user_interests(user_id)
        if interest not in interests:
            interests.append(interest)
            self._update_interests(user_id, interests)

    def remove_interest(self, user_id: int, interest: str):
        """Удаляет интерес у пользователя"""
        interests = self.get_user_interests(user_id)
        if interest in interests:
            interests.remove(interest)
            self._update_interests(user_id, interests)

    def clear_interests(self, user_id: int):
        """Очищает все интересы пользователя"""
        self._update_interests(user_id, [])

    def get_user_interests(self, user_id: int) -> list:
        """Возвращает список интересов пользователя"""
        self.cursor.execute(
            "SELECT interests FROM users WHERE id = ?",
            (user_id,)
        )
        result = self.cursor.fetchone()
        return result[0].split(',') if result and result[0] else []

    def _update_interests(self, user_id: int, interests: list):
        """Обновляет интересы пользователя в базе"""
        self.cursor.execute(
            "UPDATE users SET interests = ? WHERE id = ?",
            (','.join(interests), user_id)
        )
        self.conn.commit()

    def get_users_in_long_search(self, time_threshold: datetime):
        """Возвращает пользователей, которые в поиске дольше time_threshold"""
        self.cursor.execute(
            "SELECT * FROM users WHERE status = 1 AND search_started IS NOT NULL"
        )
        users = []
        for row in self.cursor.fetchall():
            if row['search_started']:
                started = datetime.fromisoformat(row['search_started'])
                if started < time_threshold:
                    users.append(dict(row))
        return users

    def get_expired_blocks(self, now: datetime):
        """Возвращает пользователей с истёкшим временем блокировки"""
        self.cursor.execute(
            "SELECT * FROM users WHERE blocked = 1 AND blocked_until IS NOT NULL"
        )
        users = []
        for row in self.cursor.fetchall():
            if row['blocked_until']:
                until = datetime.fromisoformat(row['blocked_until'])
                if until < now:
                    users.append(dict(row))
        return users

    def block_user(self, user_id: int, block_until: datetime = None, permanent=False):
        if permanent:
            self.cursor.execute(
                "UPDATE users SET blocked = 1, blocked_until = NULL WHERE id = ?",
                (user_id,)
            )
        else:
            until_str = block_until.isoformat() if block_until else None
            self.cursor.execute(
                "UPDATE users SET blocked = 1, blocked_until = ? WHERE id = ?",
                (until_str, user_id)
            )
        self.conn.commit()

    def unblock_user(self, user_id: int):
        self.cursor.execute(
            "UPDATE users SET blocked = 0, blocked_until = NULL WHERE id = ?",
            (user_id,)
        )
        self.conn.commit()

    def save_message(self, sender_id: int, receiver_id: int, content: str):
        self.cursor.execute(
            "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
            (sender_id, receiver_id, content)
        )
        self.conn.commit()

    def get_chat_log(self, user1_id: int, user2_id: int, limit=10):
        self.cursor.execute('''
            SELECT * FROM messages 
            WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp DESC LIMIT ?
        ''', (user1_id, user2_id, user2_id, user1_id, limit))
        return [dict(row) for row in self.cursor.fetchall()]

    def add_rating(self, user_id: int, rating: int):
        """Добавляет рейтинг пользователю: rating = 1 (положительный) или -1 (негативный)"""
        self.cursor.execute("SELECT positive, negative FROM user_ratings WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            positive, negative = row['positive'], row['negative']
            if rating > 0:
                positive += 1
            else:
                negative += 1
            self.cursor.execute(
                "UPDATE user_ratings SET positive = ?, negative = ? WHERE user_id = ?",
                (positive, negative, user_id)
            )
        else:
            positive = 1 if rating > 0 else 0
            negative = 1 if rating < 0 else 0
            self.cursor.execute(
                "INSERT INTO user_ratings (user_id, positive, negative) VALUES (?, ?, ?)",
                (user_id, positive, negative)
            )
        self.conn.commit()

    def get_user_rating(self, user_id: int):
        self.cursor.execute("SELECT positive, negative FROM user_ratings WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {"positive": row["positive"], "negative": row["negative"]}
        else:
            return {"positive": 0, "negative": 0}

    def get_last_rival(self, user_id: int):
        """Возвращает id последнего собеседника пользователя"""
        self.cursor.execute("SELECT rival_id FROM last_rivals WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row["rival_id"] if row else None

    def close(self):
        """Закрывает соединение с базой данных"""
        self.conn.close()
