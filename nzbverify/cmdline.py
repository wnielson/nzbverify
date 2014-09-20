#!/usr/bin/env python
"""
nzbverify - Weston Nielson <wnielson@github>

TODO:
    * Add missing threshold, after which we quit (default 5%?)
    * Add date range in NZB info printout
    * Add debug mode
    * Add timing info
    * Better handling of credentials
    * Check for existance of NZB file before starting threads
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
from nzbverify.server import Server

try:
    from xml.etree.cElementTree import iterparse
except:
    from xml.etree.ElementTree import iterparse


__prog__ = "nzbverify"

__usage__ = """
Usage:
    %s [options] <NZB file>

Options:
    -c <config>     : Config file to use (defaults: ~/.nzbverify, ~/.netrc)
    -l <log>        : Log messages to a specified file
    -n <log level>  : Changes the level of logging (higher values equals more logging)
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

def main(nzb, config):
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


    # Determine server priority.  We do this by considering two types of
    # servers: primary and backup.  Primary servers will be used to check for
    # all segments.  If a segment is missing from all available primary servers
    # then backup servers will be used to check for the missing segments.  Only
    # after a segment is verified as missing from all primary and backup servers
    # do we consider is a missing segment.
    primary_servers = []
    backup_servers  = []
    num_connections = 0
    for host, settings in config.items():
        if settings.get("backup", False):
            backup_servers.append(host)
        else:
            primary_servers.append(host)

        num_connections += settings.get("connections", 0)

    print "Found %d primary host%s" % (len(primary_servers), len(primary_servers) != 1 and "s" or "")
    for host in primary_servers:
        print "  ", host

    print "Found %d backup host%s" % (len(backup_servers), len(backup_servers) != 1 and "s" or "")
    for host in backup_servers:
        print "  ", host

    #print "Creating %d threads" % num_connections

    priority = 0
    for host in primary_servers:
        config[host]["priority"] = priority
        priority += 1

    for host in backup_servers:
        config[host]["priority"] = priority
        priority += 1

    # Spawn some threads
    tid = 0
    for host, settings in config.items():
        server = Server(host, settings)

        for i in range(settings.get("connections", 0)):
            try:
                t = thread.SegmentCheckerThread(tid, segments, missing, server)
                t.setDaemon(True)
                t.start()
                threads.append(t)
                tid += 1
            except:
                break

    print "Created %d/%d threads" % (tid, num_connections)

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
    print "Found %d files and %d segments totaling %s %s" % (len(files), seg_count, size, unit)

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
    print "nzbverify version %s, Copyright (C) 2014 %s" % (__version__, __author__)

    config    = None
    log_file  = None
    log_level = logging.INFO

    # Parse command line options
    opts, args = getopt.getopt(sys.argv[1:], 'c:l:n:h', ["config=", "log=", "level=", "help"])
    for o, a in opts:
        if o in ("-h", "--help"):
            print __help__
            print_usage()
            sys.exit(0)
        elif o in ("-c", "--config"):
            config = a
        elif o in ("-l", "--log"):
            log_file = a
        elif o in ("-n", "--level"):
            try:
                log_level = int(n)
            except:
                log_level = 0

            if log_level > 0:
                log_level = logging.DEBUG
            else:
                log_level = logging.INFO

    if log_file:
        logging.basicConfig(filename=log_file, level=log_level, format="%(asctime)s [%(levelname)s] - [%(threadName)10s] - %(name)s - %(message)s")

    # Get the NZB
    if len(args) < 1:
        print_usage()
        sys.exit(0)
    nzb = args[0]

    # Load NNTP details from config files
    config = conf.get_config(config)
    if not config:
        print "Error: No config file found"
        sys.exit(0)

    if len(config) < 1:
        print "Error: Didn't find any servers"
        sys.exit(0)

    start = time.time()
    main(nzb, config)
    print "Verification took %s seconds" % (time.time() - start)
