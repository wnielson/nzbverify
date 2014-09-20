import logging
import threading

import nntplib
import nntp

from Queue import Queue

log = logging.getLogger("server")

class ConnectionClosedException(Exception):
    pass

class Server(object):
    _servers = []

    def __init__(self, host, conf):
        # NNTP server information
        self.host = host
        self.conf = conf

        # Segments that are missing from higher priority servers
        self.segments = Queue()
        self.missing  = set()
        self.__mlock  = threading.RLock()

        # Add ourself to the global list of servers, ordered by priority
        self._servers.insert(conf.get("priority", 0), self)

    def log(self, f, msg):
        msg = "{%s} %s" % (self.host, msg)
        f(msg)

    def create_connection(self):
        return nntp.NNTP(self.host,                self.conf.get("port"),
                         self.conf.get("user"),    self.conf.get("password"),
                         self.conf.get("use_ssl"), self.conf.get("timeout"))

    def add_missing_segment(self, segment):
        self.__mlock.acquire()
        self.missing.add(segment)
        self.__mlock.release()

    def has_missing_segment(self, segment):
        self.__mlock.acquire()
        has = segment in self.missing
        self.__mlock.release()
        return has

    def try_next_server(self, segment, missing):
        """
        Assign a segment to the next lower priority server.  If there are no
        more servers to try, then set the segment as missing
        """
        try:
            # Pass segment off to next lower priority server
            server = self._servers[self._servers.index(self)+1]
            server.segments.put(segment)
        except:
            self.log(log.info, "Segment not available on any servers: %s" % str(segment))
            missing.put(segment)
            missing.task_done()

    def check_segment(self, connection, segment, segments, missing):
        """
        Check to see if this server has the requested segment.

        Arguments:
            connection  - NNTP connection
            segment     - Tuple of format: (file name, message id, bytes)
            segments    - Global segments queue
            missing     - Global missing segments queue

        If the NNTP connection has be closed (due to idle) will raise an
        ``ConnectionClosedException`` exception.
        """
        if self.has_missing_segment(segment):
            # We already know we don't have this segment, so send it to the
            # next server
            self.log(log.info, "Segment '%s' already marked as missing, passing off to next server" % segment[1])
            self.try_next_server(segment, missing)
            return

        f, msgid, bytes = segment

        # Check for the article on the server
        try:
            # Found the segment
            connection.stat(msgid)

            if self.conf.get("backup"):
                self.log(log.info, "Found segment '%s' on backup server" % segment[1])

        except nntplib.NNTPTemporaryError, e:
            # Error code 430 is "No such article"
            error = nntp.get_error_code(e)
            if error == '430':
                # Found missing segment.  Mark it as missing from this server
                # and pass it to the highest priority server, where it'll then
                # trickle its way down through all the servers
                self.add_missing_segment(segment)
                self._servers[0].segments.put(segment)
                return

            elif error == "400":
                # Code 400 means the connection is closed, usually do to a timeout
                raise ConnectionClosedException("Connection closed - idle timeout?")

            else:
                # Some other error, put the segment back in the
                # queue to be checked again
                log.error("Error: %s" % e)
                segments.put(segment)
                return

        except Exception, e:
            log.error("Unknown error: %s" % e)
            return
