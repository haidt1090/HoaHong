"""Save public settings locally and secrets in the operating system credential store."""
import json,os
from pathlib import Path

SERVICE='TelegramPhotoPrint'
class ConnectionStore:
    def __init__(self,base,vault=None):
        self.path=Path(base)/'telegram-connection.json'
        if vault is None:
            import keyring
            vault=keyring
        self.vault=vault
    def load(self):
        try:
            config=json.loads(self.path.read_text(encoding='utf-8'))
            if config.get('mode') not in ('bot','account'): return None
            secret=self.vault.get_password(SERVICE,config['credential_key'])
            if not secret: return None
            config['credentials']=json.loads(secret)
            config['group_id']=int(config['group_id'])
            if not isinstance(config['group_title'],str): return None
            required=('token',) if config['mode']=='bot' else ('api_id','api_hash')
            if any(not isinstance(config['credentials'].get(key),str) or not config['credentials'][key] for key in required): return None
            return config
        except (OSError,ValueError,KeyError,TypeError): return None
    def save(self,mode,credentials,group_id,group_title,auto_connect=True):
        if mode=='bot':
            secret={'token':credentials['token'].strip(),'expected_username':credentials.get('expected_username','pkhoahongbot').strip().lstrip('@')}
            identity=secret['token'].split(':')[0]
        else:
            secret={'api_id':credentials['api_id'].strip(),'api_hash':credentials['api_hash'].strip()}
            identity=secret['api_id']
        key=mode+':'+identity
        config={'version':1,'mode':mode,'credential_key':key,'group_id':int(group_id),
                'group_title':str(group_title),'auto_connect':bool(auto_connect)}
        self.vault.set_password(SERVICE,key,json.dumps(secret))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temporary,self.path)
        return config
    def forget(self):
        try: config=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError): config={}
        if config.get('credential_key'):
            # Do not discard config when removing its saved credential fails.
            self.vault.delete_password(SERVICE,config['credential_key'])
        self.path.unlink(missing_ok=True)
