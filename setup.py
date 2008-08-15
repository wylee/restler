from setuptools import setup, find_packages


setup(
    name='Restler',
    version='0.1.1.1',
    description='RESTful base controller for Pylons',
    long_description="""\
Restler is a controller for Pylons projects that provides a set of default
RESTful actions that can be overridden as needed. It also handles database
connectivity as long as a few simple rules are followed.

The Restler project is now hosted at Google Code. Please see
http://code.google.com/p/restler/ for more details, documentation, etc.

The maintenance branch for v0.1 can be found here:

http://restler.googlecode.com/svn/branches/rb-0.1/#egg=Restler-dev-0.1

Restler was extracted from the byCycle Trip Planner
(http://tripplanner.bycycle.org).

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
        'SQLAlchemy==0.3.7',
        'Elixir==0.3.0',
        'simplejson>=1.9.2',
        ),
    test_suite = 'nose.collector',
)
