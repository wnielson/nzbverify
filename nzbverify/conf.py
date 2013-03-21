import netrc
import os

DEFAULT_CONFIG_PATHS = ['~/.nzbverify', '~/.netrc']

def get_config(config=None, defaults=DEFAULT_CONFIG_PATHS):
    config_paths = []
    if config is not None:
        config_paths.append(config)
    config_paths.extend(defaults)
    
    conf = None
    for path in config_paths:
        if path.startswith('~'):
            path = os.path.expanduser(path)
        try:
            conf = netrc.netrc(path)
            break
        except:
            pass
    
    return conf
