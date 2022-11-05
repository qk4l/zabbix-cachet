from setuptools import setup

setup(
    name='zabbix-cachet',
    version='2.0.0',
    packages=['zabbix_cachet'],
    package_dir={'': 'src'},
    url='https://github.com/qk4l/zabbix-cachet',
    license='MIT License',
    author='Artem Aleksandrov',
    author_email='qk4l@tem4uk.ru',
    description='Python daemon which provides synchronisation between Zabbix IT Services and Cachet',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.21.0",
        # TODO: Check versions!
        "PyYAML==6.0",
        "pyzabbix==1.2.1",
        "pytz",
    ],
)
