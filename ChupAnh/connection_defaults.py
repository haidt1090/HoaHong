"""Load private editable defaults. This module itself contains no token."""
import os,sys

def default_connection():
    if os.environ.get('CHUPANH_OFFLINE_TEST')=='1' or '--smoke-test' in sys.argv: return None
    try:
        from private_defaults import DEFAULT_BOT_TOKEN,DEFAULT_BOT_USERNAME,DEFAULT_GROUP_ID,DEFAULT_GROUP_TITLE,DEFAULT_AUTO_CONNECT
    except ImportError: return None
    if not DEFAULT_BOT_TOKEN: return None
    return {'mode':'bot','credentials':{'token':DEFAULT_BOT_TOKEN,'expected_username':DEFAULT_BOT_USERNAME},
            'group_id':int(DEFAULT_GROUP_ID),'group_title':DEFAULT_GROUP_TITLE,'auto_connect':DEFAULT_AUTO_CONNECT}

def seed_needs_apply(base,seed):
    import hashlib,json
    from pathlib import Path
    revision=hashlib.sha256(json.dumps(seed,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=Path(base)/'private-defaults.revision'
    try: applied=path.read_text(encoding='ascii').strip()==revision
    except OSError: applied=False
    return not applied,path,revision
