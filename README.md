# nzbverify

`nzbverify` is a command-line tool and library for verifying the integrity of
an NZB file.  It is capable of supporting both standard and SSL-encrypted NNTP
connections and employs threads for increased verification speed.

## Usage

```
nzbverify -s news.server.com -u myusername -p mypassword -n40 test.nzb 
nzbverify version 0.2.1, Copyright (C) 2012 Weston Nielson <wnielson@github>
Created 40 threads
Parsing NZB: test.nzb
Found 207 files and 27866 segments totalling 10.31 GB
Available: 26632 [100.00%], Missing:     0 [0.00%], Total: 26632 [100.00%]
Result: all 27866 segments available
Verification took 12.1951680183 seconds
```
