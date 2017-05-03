#!/usr/bin/env python
"""
nzbverify - Weston Nielson <wnielson@github>

TODO:
    * Add missing threshold, after which we quit (default 5%?)
    * Add date range in NZB info printout
    * Add debug mode
    * Add timing info
    * Add SSL support
    * Better handling of credentials
    * Use getopt
    * Check for existance of NZB file before starting threads
    * Enable default config files (~/.nzbverify, ~/.netrc)
"""
from __future__ import division

import Queue
import getopt
import getpass
import logging
import netrc
import nntplib
import os
import signal
import sys
import time

sys.path.append('../')

from nzbverify import __author__, __version__, conf, thread

try:
    from xml.etree.cElementTree import iterparse
except:
    from xml.etree.ElementTree import iterparse

__prog__ = "nzbverify"

__usage__ = """
Usage:
    %s [options] <NZB file>

Options:
    -s<server>      : NNTP server
    -u<username>    : NNTP username
    -p              : NNTP password, will be prompted for
    -P<port>        : NNTP port
    -c<config>      : Config file to use (defaults: ~/.nzbverify, ~/.netrc)
    -n<threads>     : Number of NNTP connections to use
    -e              : Use SSL/TLS encryption
    -h              : Show help text and exit
"""

__help__ = """
Help text...
"""

DEFAULT_NUM_CONNECTIONS = 5

def get_size(bytes):
    size = bytes/1048576.0
    unit = "MB"
    if len(str(round(size))) > 3:
        size = size / 1024.0
        unit = "GB"
    return "%0.2f" % size, unit

class ProgressBar(object):
    def __init__(self, segments, missing):
        self.segments = segments
        self.missing = missing
        self.segment_count = segments.qsize()
        
        digits = len(str(self.segment_count))
        self._msg = ("Available: %%0%ds [%%s], "
                     "Missing: %%0%ds [%%s], "
                     "Total: %%0%ds [%%s]" %
                     (digits,digits,digits))
    
    def update(self):
        tnum = self.segment_count - self.segments.qsize()
        tpct = "%0.2f%%" % ((tnum/self.segment_count)*100.00)
        mnum = self.missing.qsize()
        mpct = "%0.2f%%" % ((mnum/self.segment_count)*100.00)
        anum = tnum-mnum
        apct = "%0.2f%%" % ((anum/self.segment_count)*100.00)
        msg = self._msg % (anum, apct, mnum, mpct, tnum, tpct)
        sys.stdout.write("\r%s" % msg)
        sys.stdout.flush()
    
    def finish(self):
        self.update()
        sys.stdout.write("\n")

def main(nzb, num_connections, nntp_kwargs):    
    threads     = []
    files       = []
    seg_count   = 0
    bytes_total = 0
    segments    = Queue.Queue()
    missing     = Queue.Queue()
    
    # Listen for exit
    def signal_handler(signal, frame):
        sys.stdout.write('\n')
        sys.stdout.write("Stopping threads...")
        sys.stdout.flush()
        thread.stop_threads(threads)
        sys.stdout.write("done\n")
        sys.exit(0)
    
    # TODO: Listen to other signals
    signal.signal(signal.SIGINT, signal_handler)
    
    # Spawn some threads
    for i in range(num_connections):
        try:
            t = thread.SegmentCheckerThread(i, segments, missing, nntp_kwargs)
            t.setDaemon(True)
            t.start()
            threads.append(t)
        except:
            break
    
    print "Created %d threads" % (i+1)
    
    # Parse NZB and populate the Queue
    print "Parsing NZB: %s" % nzb
    for event, elem in iterparse(nzb, events=("start", "end")):
        if event == "start" and elem.tag.endswith('file'):
            files.append(elem.get('subject'))
        if event == "end" and elem.tag.endswith('segment'):
            bytes = int(elem.get('bytes',0))
            bytes_total += bytes
            segments.put((files[-1], '<%s>' % elem.text, bytes))
            seg_count += 1
    
    size, unit = get_size(bytes_total)
    print "Found %d files and %d segments totalling %s %s" % (len(files), seg_count, size, unit)
    
    pbar = ProgressBar(segments, missing)
    
    while not segments.empty():
        pbar.update()
        time.sleep(0.1)
    
    pbar.finish()
    
    missing.join()
    
    num_missing = missing.qsize()
    if num_missing > 0:
        missing_bytes = 0
        print "Result: missing %d/%d segments; %0.2f%% complete" % (num_missing, seg_count, ((seg_count-num_missing)/seg_count * 100.00))
        while not missing.empty():
            f, seg, bytes = missing.get()
            missing_bytes += bytes
            print '\tfile="%s", segment="%s"' % (f, seg)
        
        size, unit = get_size(missing_bytes)
        print "Missing %s %s" % (size, unit)
    else:
        print "Result: all %d segments available" % seg_count
    
    thread.stop_threads(threads)

def print_usage():
    print __usage__ % __prog__

def run():
    print "nzbverify version %s, Copyright (C) 2012 %s" % (__version__, __author__)
        
    num_connections = DEFAULT_NUM_CONNECTIONS
    config          = None
    nntp_kwargs     = {
        'host':     None,
        'port':     nntplib.NNTP_PORT,
        'user':     None,
        'password': None,
        'use_ssl':  None,
        'timeout':  10
    }
    
    # Parse command line options
    opts, args = getopt.getopt(sys.argv[1:], 's:u:P:n:c:eph', ["server=", "username=",  "port=", "connections=", "config=", "ssl", "password", "help"])
    for o, a in opts:
        if o in ("-h", "--help"):
            print __help__
            print_usage()
            sys.exit(0)
        elif o in ("-s", "--server"):
            nntp_kwargs['host'] = a
        elif o in ("-u", "--username"):
            nntp_kwargs['user'] = a
        elif o in ("-p", "--password"):
            nntp_kwargs['password'] = getpass.getpass("Password: ")
        elif o in ("-e", "--ssl"):
            nntp_kwargs['use_ssl'] = True
        elif o in ("-P", "--port"):
            try:
                nntp_kwargs['port'] = int(a)
            except:
                print "Error: invalid port '%s'" % a
                sys.exit(0)
        elif o in ("-n", "--connections"):
            try:
                num_connections = int(a)
            except:
                print "Error: invalid number of connections '%s'" % a
                sys.exit(0)
        elif o in ("-c", "--config"):
            config = a
    
    # Get the NZB
    if len(args) < 1:
        print_usage()
        sys.exit(0)
    nzb = args[0]
    
    # See if we need to load certain NNTP details from config files
    # A host is required
    config = conf.get_config(config)
    if not nntp_kwargs['host'] and not config:
        print "Error: no server details provided"
        sys.exit(0)
    
    if config:
        credentials = config.authenticators(nntp_kwargs.get('host'))
        if not credentials:
            if not config.hosts:
                print "Error: Could not determine server details"
                sys.exit(0)
            
            # Just use the first entry
            host, credentials = config.hosts.items()[0]
            nntp_kwargs['host'] = host
        
        if not nntp_kwargs['user'] and not nntp_kwargs['password']:
            nntp_kwargs['user'] = credentials[0]
            nntp_kwargs['password'] = credentials[2]
    
    start = time.time()
    main(nzb, num_connections, nntp_kwargs)
    print "Verification took %s seconds" % (time.time() - start)
