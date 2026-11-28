"""Settings for this agent. The only file that differs between agent folders."""
import os

AGENT = "icu-management-agent"
SUFFIX = "ICU"

HOSPITAL_ID = os.getenv("HOSPITAL_ID", "H001")
NODE_DB_URL = os.getenv("NODE_DB_URL")    # postgresql://user:pass@node-db-h001:5432/node_h001

PING_REQUESTS_TOPIC = "hrc.ping.requests"
PING_REPLIES_TOPIC = "hrc.ping.replies"