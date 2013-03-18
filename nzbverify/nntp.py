import logging
import nntplib
import socket

try:
    import ssl
except ImportError:
    _have_ssl = False
else:
    _have_ssl = True

log = logging.getLogger('NNTP')

# Add the 'CAPABILITIES' response
nntplib.LONGRESP.append('101')

SSL_PORTS = [443, 563]

def get_error_code(error):
    """
    Attempts to extract the NNTP error code number from an NNTPError, which
    are of the form:
    
        430 No such article
    """
    error = str(error)
    return error.split()[0]

class NNTP(nntplib.NNTP):
    """
    An NNTP client that supports SSL/TLS.  Most of this code is back-ported from
    Python 3.2 (see source below).
  
    NOTE: SSL support has been tested but TLS support has not.
  
    Source:
        http://svn.python.org/view/python/branches/release32-maint/Lib/nntplib.py
    """
    def __init__(self, host, port, user=None, password=None, use_ssl=None,
                 timeout=10):
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port), timeout)
        self.sock = self.wrap_socket(self.sock, use_ssl)
        self.file = self.sock.makefile('rrb')
        self.debugging  = 0
        self.welcome    = self.getresp()
        self._caps      = None
        self.authenticated = False

        # RFC 4642 2.2.2: Both the client and the server MUST know if there is
        # a TLS session active.  A client MUST NOT attempt to start a TLS
        # session if a TLS session is already active.
        self.tls_on = False

        # If TLS is supported start a TLS session.  Note that we have to do this
        # before we try to authenticate.
        if 'STARTTLS' in self.getcapabilities():
            self.starttls()
    
        # Perform authentication if needed.
        if user:
            self.login(user, password)
  
    def login(self, user, password):
        if self.authenticated:
            raise ValueError("Already logged in.")

        if user:
            resp = self.shortcmd('authinfo user ' + user)
            if resp[:3] == '381':
                if not password:
                    raise nntplib.NNTPReplyError(resp)
                else:
                    resp = self.shortcmd('authinfo pass ' + password)
                    if resp[:3] != '281':
                        raise nntplib.NNTPPermanentError(resp)

        self.authenticated = True
  
    def starttls(self, context=None):
        """
        Process a STARTTLS command. Arguments:
            - context: SSL context to use for the encrypted connection
        """
        # Per RFC 4642, STARTTLS MUST NOT be sent after authentication or if
        # a TLS session already exists.
        if _have_ssl:
            if self.tls_on:
                raise ValueError("TLS is already enabled.")
            if self.authenticated:
                raise ValueError("TLS cannot be started after authentication.")
            resp = self._shortcmd('STARTTLS')
            if resp.startswith('382'):
                self.file.close()
                self.sock = self.wrap_socket(self.sock)
                self.file = self.sock.makefile("rwb")
                self.tls_on = True
                # Capabilities may change after TLS starts up, so ask for them
                # again.
                self._caps = None
                self.getcapabilities()
            else:
                raise nntplib.NNTPError("TLS failed to start.")
  
    def getcapabilities(self):
        """
        If the CAPABILITIES command is not supported, an empty dict is
        returned.
        """
        if self._caps is None:
            self.nntp_version = 1
            self.nntp_implementation = None
            try:
                resp, caps = self.capabilities()
            except nntplib.NNTPPermanentError:
                # Server doesn't support capabilities
                self._caps = {}
        else:
            self._caps = caps
            if 'VERSION' in caps:
                # The server can advertise several supported versions,
                # choose the highest.
                self.nntp_version = max(map(int, caps['VERSION']))
            if 'IMPLEMENTATION' in caps:
                self.nntp_implementation = ' '.join(caps['IMPLEMENTATION'])
        return self._caps
  
    def capabilities(self):
        """
        Process a CAPABILITIES command.  Not supported by all servers.
        """
        caps = {}
        resp, lines = self.longcmd("CAPABILITIES")
        for line in lines:
            bits = line.split()
            name, tokens = bits[0], bits[1:]
            caps[name] = tokens
        return resp, caps
  
    def wrap_socket(self, sock, use_ssl):
        """
        Wrap a socket in SSL/TLS. Arguments:
            - sock: Socket to wrap

        Returns:
            - sock: New, encrypted socket.
        """
        # If the user hasn't explicitly said no to SSL, we'll use SSL if the port
        # is a known-SSL port.
        if use_ssl is None and self.port in SSL_PORTS:
            use_ssl = True

        if _have_ssl and use_ssl:
            log.debug("Using SSL")
            return ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLSv1)
        return sock
