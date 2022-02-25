#!/usr/bin/python3
'''python-dbusmock - Mock D-Bus objects for testing'''

import setuptools

with open('README.md', encoding="UTF-8") as f:
    readme = f.read()

with open('NEWS', 'r', encoding="UTF-8") as f:
    version = f.readline().split('[')[1].split(']')[0]

setuptools.setup(
    name='python-dbusmock',
    version=version,
    description='Mock D-Bus objects',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='Martin Pitt',
    author_email='martin.pitt@ubuntu.com',
    url='https://github.com/martinpitt/python-dbusmock',
    download_url='https://pypi.python.org/pypi/python-dbusmock/',
    license='LGPL 3+',
    packages=['dbusmock', 'dbusmock.templates'],

    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Environment :: Other Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        'Operating System :: Unix',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
