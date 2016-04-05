# Zabbix-Cachet
This is python script which provide synchronisation between [Zabbix IT Services](https://www.zabbix.com/documentation/3.0/manual/it_services)
and [Cachet](https://cachethq.io/)

# Description

The idea of Zabbix-Cachet is providing the easiest way to export Zabbix terms to Cachet.
With this script you can maintain Cachet though Zabbix.

Zabbix-Cachet reads pre-configured [Zabbix IT Services](https://www.zabbix.com/documentation/3.0/manual/it_services) and automatically creates Cachet components.
After that Zabbix-Cachet periodically checks Zabbix triggers (that linked to you IT Services) and manipulate with Cachet incidents and Component statuses based on triggers.

# Features
* Automatically creates Cachet Components and Components group
* Automatically creates Cachet Incidents and update them with [acknowleddgment messages](https://www.zabbix.com/documentation/3.0/manual/acknowledges)
* Allow to specify root IT service where Zabbix-Cachet will work


# Installation
1. Clone this repository
2. Rename `config-example.yml` to `config.yml` and fill a file with your settings.
3. Install python libs from `requirements.txt`
4. Launch `zabbix-cachet.py`

# Docker Installation
1. Create `/etc/zabbix-cachet.yml` file based `config-example.yml`.
2. Run Docker container
```
docker run --name zabbix-cachet -v /etc/zabbix-cachet.yml:/config.yml qk4l/zabbix-cachet
```
3. Drink a cup of tea (optional)

# Configuration

Settings are storing in `config.yml` file which should be placed in script's working directory.
If you want to use another path for `config.yml` use `ZABBIX-CACHET-CONF` environment variable.