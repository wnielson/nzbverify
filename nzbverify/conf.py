import netrc
import os

DEFAULT_CONFIG_PATHS = ['~/.nzbverify', '~/.netrc']

def get_config(config=None):
    config_paths = []
    if config is not None:
        config_paths.append(config)
    config_paths.extend(DEFAULT_CONFIG_PATHS)
    
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