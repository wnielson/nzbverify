import threading
import nntp
import nntplib

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
    def __init__(self, num, segments, missing, credentials):
        threading.Thread.__init__(self)
        self.num          = num
        self.segments     = segments        # Queue.Queue
        self.missing      = missing         # Queue.Queue
        self.credentials  = credentials
        self.stop         = False           # Set to True to stop thread
        
    def run(self):
        self.server = nntp.NNTP(**self.credentials)
        try:
            while True:
                if self.stop:
                    self.server.quit()
                    return
                
                # Try to grab a segment from queue
                f, segment, bytes = self.segments.get(False)
                
                # Check for the article on the server
                try:
                    self.server.stat(segment)
                    #print "Found: %s" % segment
                except nntplib.NNTPTemporaryError, e:
                    # Error code 430 is "No such article"
                    error = nntp.get_error_code(e)
                    if error == '430':
                        # Found missing segment                    
                        self.missing.put((f, segment, bytes))
                        self.missing.task_done()
                        #print "Missing: %s" % segment
                    else:
                        # Some other error, put the segment back in the
                        # queue to be checked again
                        print "Error: %s" % e
                        self.segments.put(segment)
                except Exception, e:
                    print "Unknown error: %s" % e
                    return
                
                # Signals to queue that this task is done
                self.segments.task_done()
        except Exception, e:
            try:
                self.server.quit()
            except:
                pass