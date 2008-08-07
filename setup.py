from setuptools import setup, find_packages


setup(
    name='Restler',
    version='0.2a10',
    description="""\
RESTful base controller for Pylons 0.9.7 (no Elixir dependency; uses \
"straight" SQLAlchemy)""",
    long_description="""\
Restler is a controller for Pylons projects that provides a set of default
RESTful actions that can be overridden as needed. It also handles database
connectivity as long as a few simple rules are followed.

The Restler project is hosted at Google Code. Please see
http://code.google.com/p/restler/ for more details, documentation, etc.

Restler was originally extracted from the byCycle bicycle trip planner
(http://bycycle.org).

""",
    license='BSD/MIT',
    author='Wyatt L Baldwin',
    author_email='self@wyattbaldwin.com',
    keywords='web pylons controller REST WSGI',
    url='http://code.google.com/p/restler/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Paste',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
    ],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=(
        'SQLAlchemy>=0.5beta3',
        'simplejson>=1.9.2',
    ),
    test_suite = 'nose.collector',
)
