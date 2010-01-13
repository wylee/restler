from setuptools import setup, find_packages


version = '0.3.3'


setup(
    name='Restler',
    version=version,
    description="""RESTful base controller for Pylons 0.9.7.""",
    long_description="""\
Restler is a controller for Pylons projects that provides a set of default
RESTful actions that can be overridden as needed.

The Restler project is hosted at Google Code. Please see
http://code.google.com/p/restler/ for more details, documentation, etc.

The latest development version can be found here:

http://restler.googlecode.com/svn/trunk/#egg=Restler-dev

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
        'Framework :: Pylons',
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
        'decorator>=3.1.2',
        'SQLAlchemy>=0.5.7',
    ),
    test_suite = 'nose.collector',
)

