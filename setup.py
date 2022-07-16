#!/usr/bin/python3
# this setup.py exists for the benefit of RPM builds. Doing that with PyPA build
# is completely busted still.

'''python-dbusmock - Mock D-Bus objects for testing'''

import setuptools

with open('README.md', encoding="UTF-8") as f:
    readme = f.read()

setuptools.setup(
    name='python-dbusmock',
    version="0.28.2",
    description='Mock D-Bus objects',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Martin Pitt',
    author_email='martin@piware.de',
    url='https://github.com/martinpitt/python-dbusmock',
    download_url='https://pypi.python.org/pypi/python-dbusmock/',
    license='LGPL 3+',
    packages=['dbusmock', 'dbusmock.templates'],
    install_requires=[
        'dbus-python',
    ],

    classifiers=[
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python :: 3",
        "Development Status :: 6 - Mature",
        "Operating System :: POSIX :: Linux",
        "Operating System :: POSIX :: BSD",
        "Operating System :: Unix",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Testing :: Mocking",
        "Topic :: Software Development :: Testing :: Unit",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
