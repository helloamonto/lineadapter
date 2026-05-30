import os
import json
import hmac
import hashlib
import base64
import logging
import urllib.request
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Config ---
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "your_channel_secret_here")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

# --- In-memory message store (resets on restart) ---
messages = []


def get_user_profile(user_id: str) -> dict:
    """Fetch display name and picture from LINE Profile API."""
    try:
        url = f"https://api.line.me/v2/bot/profile/{user_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"})
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Could not fetch profile for {user_id}: {e}")
        return {}

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def verify_signature(body: bytes, signature: str) -> bool:
    hash = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(hash).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def log_event(event: dict):
    event_type = event.get("type", "unknown")
    timestamp = datetime.utcnow().isoformat()
    source = event.get("source", {})
    user_id = source.get("userId", "unknown")

    profile = get_user_profile(user_id)
    record = {
        "timestamp": timestamp,
        "event_type": event_type,
        "user_id": user_id,
        "display_name": profile.get("displayName", "unknown"),
        "picture_url": profile.get("pictureUrl", ""),
    }

    if event_type == "message":
        msg = event.get("message", {})
        msg_type = msg.get("type")
        record["message_type"] = msg_type
        record["text"] = msg.get("text") if msg_type == "text" else None
        logger.info(f"[{timestamp}] TEXT from {user_id}: {msg.get('text')}" if msg_type == "text" else f"[{timestamp}] {msg_type.upper()} from {user_id}")

    elif event_type == "follow":
        logger.info(f"[{timestamp}] NEW FOLLOWER: {user_id}")

    elif event_type == "unfollow":
        logger.info(f"[{timestamp}] UNFOLLOWED by: {user_id}")

    elif event_type == "postback":
        data = event.get("postback", {}).get("data", "")
        record["postback_data"] = data
        logger.info(f"[{timestamp}] POSTBACK from {user_id}: {data}")

    else:
        logger.info(f"[{timestamp}] EVENT [{event_type}]: {json.dumps(event)}")

    messages.append(record)
    if len(messages) > 500:  # keep last 500 messages
        messages.pop(0)


# --- Routes ---

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data()

    if not verify_signature(body, signature):
        logger.warning("Invalid signature received")
        return jsonify({"error": "Invalid signature"}), 403

    try:
        payload = json.loads(body)
        events = payload.get("events", [])
        for event in events:
            log_event(event)
    except Exception as e:
        logger.error(f"Error processing events: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/debug/profile/<user_id>", methods=["GET"])
def debug_profile(user_id):
    token = CHANNEL_ACCESS_TOKEN
    profile = get_user_profile(user_id)
    return jsonify({
        "token_set": bool(token),
        "token_preview": token[:10] + "..." if token else "EMPTY",
        "profile_result": profile
    }), 200


@app.route("/messages", methods=["GET"])
def get_messages():
    event_type = request.args.get("type")        # filter by event type
    user_id = request.args.get("user_id")        # filter by user
    limit = int(request.args.get("limit", 50))   # default last 50

    result = messages
    if event_type:
        result = [m for m in result if m["event_type"] == event_type]
    if user_id:
        result = [m for m in result if m["user_id"] == user_id]

    return jsonify({
        "total": len(result),
        "messages": result[-limit:]
    }), 200


@app.route("/privacy", methods=["GET"])
def privacy():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Privacy Policy - amonto</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
            h1 { color: #06C755; }
            h2 { margin-top: 30px; }
        </style>
    </head>
    <body>
        <h1>Privacy Policy</h1>
        <p><strong>Last updated:</strong> May 2026</p>

        <h2>1. Information We Collect</h2>
        <p>When you interact with our LINE Official Account, we may collect:</p>
        <ul>
            <li>LINE User ID</li>
            <li>Messages and content you send to us</li>
            <li>Profile information (display name, profile photo) when you follow our account</li>
        </ul>

        <h2>2. How We Use Your Information</h2>
        <p>We use the information collected to:</p>
        <ul>
            <li>Respond to your messages and inquiries</li>
            <li>Improve our service and user experience</li>
            <li>Send relevant notifications and updates</li>
        </ul>

        <h2>3. Data Sharing</h2>
        <p>We do not sell, trade, or share your personal information with third parties except as required by law.</p>

        <h2>4. Data Retention</h2>
        <p>We retain your data only as long as necessary to provide our services. You may request deletion at any time.</p>

        <h2>5. Your Rights</h2>
        <p>You may request access to, correction of, or deletion of your personal data by contacting us.</p>

        <h2>6. Contact</h2>
        <p>For privacy-related inquiries, please contact us via our LINE Official Account: <strong>@200wfxtj</strong></p>
    </body>
    </html>
    """, 200


@app.route("/terms", methods=["GET"])
def terms():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terms of Service - amonto</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
            h1 { color: #06C755; }
            h2 { margin-top: 30px; }
        </style>
    </head>
    <body>
        <h1>Terms of Service</h1>
        <p><strong>Last updated:</strong> May 2026</p>

        <h2>1. Acceptance of Terms</h2>
        <p>By using our LINE Official Account, you agree to these Terms of Service.</p>

        <h2>2. Use of Service</h2>
        <p>You agree to use this service only for lawful purposes and in a manner that does not infringe the rights of others.</p>

        <h2>3. Prohibited Conduct</h2>
        <ul>
            <li>Sending spam or unsolicited messages</li>
            <li>Attempting to hack or disrupt the service</li>
            <li>Impersonating other users or entities</li>
        </ul>

        <h2>4. Limitation of Liability</h2>
        <p>We are not liable for any indirect, incidental, or consequential damages arising from your use of this service.</p>

        <h2>5. Changes to Terms</h2>
        <p>We reserve the right to modify these terms at any time. Continued use of the service constitutes acceptance of updated terms.</p>

        <h2>6. Contact</h2>
        <p>For questions about these terms, contact us via LINE Official Account: <strong>@200wfxtj</strong></p>
    </body>
    </html>
    """, 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "LINE Webhook Server is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
