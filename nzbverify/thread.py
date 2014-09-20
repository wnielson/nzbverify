import logging
import threading
import nntp
import nntplib

from server import ConnectionClosedException

log = logging.getLogger("thread")

def stop_threads(threads):
    """
    Stops all threads and disconnects each NNTP connection.
    """
    for thread in threads:
        thread.stop = True
        thread.join()

class SegmentCheckerThread(threading.Thread):
    """
    Threaded NZB Segment Checker.
    """
    def __init__(self, id, segments, missing, server):
        self.id         = id
        self.segments   = segments        # Queue.Queue
        self.missing    = missing         # Queue.Queue
        self.server     = server
        self.stop       = False           # Set to True to stop thread

        threading.Thread.__init__(self, name="thread-%d" % id)

    def run(self):
        connection = self.server.create_connection()
        try:
            while True:
                if self.stop:
                    connection.quit()
                    return

                segment = None
                q       = None

                if self.server.conf.get("backup", False):
                    # Backup server - only check for segments that have been
                    # explcitly passed to us
                    try:
                        segment = self.server.segments.get(True, 1)
                        q       = self.server.segments
                    except:
                        pass

                else:
                    # Try to get a segment from the server's segment queue
                    try:
                        segment = self.server.segments.get(False)
                        q       = self.server.segments
                    except:
                        # Try to grab a segment from the global queue
                        segment = self.segments.get(False)
                        q       = self.segments

                if not segment:
                    continue

                try:
                    self.server.check_segment(connection, segment, self.segments, self.missing)
                except ConnectionClosedException, e:
                    connection = self.server.create_connection()
                except Exception, e:
                    log.error("Unknown error: %s" % e)

                if q:
                    q.task_done()

        except Exception, e:
            try:
                connection.quit()
            except:
                pass
