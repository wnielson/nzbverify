from distutils.core import setup

import nzbverify

setup(
    name='nzbverify',
    version=nzbverify.__version__,
    author=nzbverify.__author__.rsplit(' ', 1)[0],
    author_email=nzbverify.__author__.split(' ', 2)[-1],
    packages=['nzbverify'],
    url='http://pypi.python.org/pypi/nzbverify/',
    license='LICENSE',
    description='Utility for verifying the completeness of an NZB.',
    long_description=open('README').read(),
    scripts=['bin/nzbverify']
)