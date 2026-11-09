"""Bot identity restriction verified using Telegram getMe, not the token label."""
ALLOWED_BOT_USERNAME='pkhoahongbot'
def allowed_bot(user):
    return str(user.get('username') or '').lstrip('@').casefold()==ALLOWED_BOT_USERNAME
