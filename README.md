# Zabbix-Cachet
This is python script which provide synchronisation between [Zabbix IT Services](https://www.zabbix.com/documentation/3.0/manual/it_services)
and [Cachet](https://cachethq.io/)

# Description

The idea of Zabbix-Cachet is providing the easiest way to export Zabbix terms to Cachet.
With this script you can maintain Cachet though Zabbix.

Zabbix-Cachet reads pre-configured [Zabbix IT Services](https://www.zabbix.com/documentation/3.0/manual/it_services) and automatically creates Cachet components.
After that Zabbix-Cachet periodically checks Zabbix triggers (that linked to you IT Services) and manipulate with Cachet incidents and Component statuses based on triggers.

Zabbix-Cachet communicate with Zabbix and Cachet via API interface.
To make it works you need a zabbix user with sufficient permissions to read triggers,
items of services that is exported to Cachet and Cachet`s API key.


# Features
* Automatically creates Cachet Components and Components group
* Automatically creates Cachet Incidents and update them with [acknowledgement messages](https://www.zabbix.com/documentation/3.0/manual/acknowledges)
* Allow to specify root IT service where Zabbix-Cachet will work

# Example
## Zabbix IT Services.
* _Cachet_ - `root_service` for zabbix-cachet script.
* _Bitbucket_, _Network Connectivity_ - parent services. They will be _Components Groups_ in Cachet.
* _GIT https_, _GIT ssh_ - Components in Cachet. Do not forget to set Zabbix trigger to this group.

![Zabbix IT Services](https://cloud.githubusercontent.com/assets/8394059/14297272/0b79bc1a-fb8f-11e5-820f-5460cc735cda.png)

## Cachet
![Cachet Components](https://cloud.githubusercontent.com/assets/8394059/14298058/c5c8b806-fb93-11e5-83f6-ff32aeb5fb4d.png)

# Requirements
Here are version that was successfully tested:
* Cachet 2.2, 2.3, 2.4, 2.5
* Zabbix 2.2, 2.4, 3.0, 3.2, 4.0, 4.2, 5.2
* python 2.7+

# Installation

# Docker Installation
1. Create `/etc/zabbix-cachet.yml` file based `config-example.yml`.
2. Run Docker container
    ```
    docker run --name zabbix-cachet -v /etc/zabbix-cachet.yml:/config.yml qk4l/zabbix-cachet
    ```
3. Drink a cup of tea (optional)

## Git
1. Clone this repository
2. Rename `config-example.yml` to `config.yml` and fill a file with your settings.
3. Install python libs from `requirements.txt`
4. Launch `zabbix-cachet.py`

## Apt
1. Add official Zabbix-Cachet [PPA](https://launchpad.net/~reg-tem4uk/+archive/ubuntu/zabbix-cachet):
    ```bash
    add-apt-repository ppa:reg-tem4uk/zabbix-cachet
    apt-get update
    ```
2. Install the package: `apt-get install zabbix-cachet`
3. Configure it: `nano /etc/zabbix-cachet.yml`
4. Restart it: `systemctl enable zabbix-cachet && systemctl restart zabbix-cachet`

# Configuration

Settings are storing in `config.yml` file which should be placed in script's working directory.
If you want to use another path for `config.yml` use `CONFIG_FILE` environment variable.
