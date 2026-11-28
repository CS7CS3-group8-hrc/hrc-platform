"""Node DB access, repository/dao."""
import psycopg


class PingRepository:
    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = None

    def save(self, message, agent, hospital_id, correlation_id):
        """Insert one row; a repeated correlation_id is ignored, so replays are harmless."""
        try:
            with self._connection().cursor() as cur:
                cur.execute(
                    "INSERT INTO ping_log (message, agent, hospital_id, correlation_id) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (correlation_id) DO NOTHING",
                    (message, agent, hospital_id, correlation_id),
                )
        except Exception:
            self.conn = None                  # reconnect on the next call
            raise

    def _connection(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg.connect(self.db_url, autocommit=True)
        return self.conn