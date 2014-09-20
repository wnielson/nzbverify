import netrc
import os
import re

DEFAULT_CONFIG_PATHS = ['~/.nzbverify', '~/.netrc']

CONF_REGEXS = {
    "port":        (re.compile(r"port=([\d]+)"),        int,),
    "connections": (re.compile(r"connections=([\d]+)"), int,),
    "backup":      (re.compile(r"backup=(true|false)"), lambda v: v.lower()[0] == "t",),
    "use_ssl":     (re.compile(r"ssl=(true|false)"),    lambda v: v.lower()[0] == "t",),
    "timeout":     (re.compile(r"timeout=([\d]+)"),     int)
}

def get_config(config=None, defaults=DEFAULT_CONFIG_PATHS):
    hosts = {}

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

    if conf:
        for host, values in conf.hosts.items():
            hosts[host] = {
                "user":         values[0],
                "password":     values[2],
                "port":         119,
                "connections":  0,
                "backup":       False,
                "use_ssl":      False
            }

            for k, v in CONF_REGEXS.items():
                m = v[0].search(values[1])
                if m:
                    hosts[host][k] = v[1](m.groups()[0])

    return hosts
