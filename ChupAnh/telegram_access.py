"""Telegram access restriction; the approved phone is stored only as a salted one-way check."""
import re,hashlib,hmac
ALLOWED_BOT_USERNAME='pkhoahongbot'
ACCOUNT_SALT=bytes.fromhex('a4ee5797679f4d0f073333bd9fbfb8e5cf2511c26e7a998efc5c6d7943ed24b9')
ACCOUNT_FINGERPRINT='e8cf4a6dd38b31921c6a4a5a64f8bc64097ed1c3c5008596c77da3bdbf416ef8'

def normalize_phone(value):
    digits=re.sub(r'\D','',str(value or ''))
    if digits.startswith('00'): digits=digits[2:]
    if digits.startswith('0'): digits='84'+digits[1:]
    return digits

def phone_fingerprint(value):
    return hashlib.scrypt(normalize_phone(value).encode('ascii'),salt=ACCOUNT_SALT,n=32768,r=8,p=1,maxmem=64*1024*1024,dklen=32).hex()

def allowed_bot(user,expected_username=ALLOWED_BOT_USERNAME):
    expected=str(expected_username).strip().lstrip('@').casefold()
    return bool(expected) and str(user.get('username') or '').lstrip('@').casefold()==expected

def allowed_account(phone):
    value=normalize_phone(phone)
    if not value.isascii() or not 10<=len(value)<=15: return False
    return hmac.compare_digest(phone_fingerprint(value),ACCOUNT_FINGERPRINT)
