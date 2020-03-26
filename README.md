# Fit.ly
Web analytics for endurance athletes
![Image description](https://i.imgur.com/CENhmnq.png)
![Image description](https://i.imgur.com/sWtC3aJ.png)
![Image description](https://i.imgur.com/fox1PBV.png)
![Image description](https://i.imgur.com/4Td0RuG.png)
![Image description](https://i.imgur.com/8HsX8KQ.png)


Special thanks to Slapdash for helping organize!
https://github.com/ned2/slapdash

## Installation

After cloning/downloading the repository, simply install Fit.ly as a package into your target virtual environment:

    $ pip install PATH_TO_fitly

During development you will likely want to perform an editable install so that
changes to the source code take immediate effect on the installed package.

    $ pip install -e PATH_TO_fitly


## Running Your App

This project comes with two convenience scripts for running your project in
development and production environments, or you can use your own WSGI server to
run the app.


### Run Your App Locally (Dev App) 

Installing this package into your virtualenv will result into the development
executable being installed into your path when the virtualenv is activated. This
command invokes your Dash app's `run_server` method, which in turn uses the
Flask development server to run your app. The command is invoked as follows:

    $ run-fitly-dev

The script takes a couple of arguments optional parameters, which you can
discover with the `--help` flag. You may need to set the port using the `--port`
parameter. If you need to expose your app outside your local machine, you will
want to set `--host 0.0.0.0`.


### Run Prod App

While convenient, the development webserver should *not* be used in
production. Installing this package will also result in a production executable
being installed in your virtualenv. This is a wrapper around the
`mod_wsgi-express` command, which streamlines use of the [mod_wsgi Apache
module](https://pypi.org/project/mod_wsgi/) to run your your app. In addition to
installing the `mod_wsgi` Python package, you will need to have installed
Apache. See installation instructions in the [mod_wsgi
documentation](https://pypi.org/project/mod_wsgi/). This script also takes a
range of command line arguments, which can be discovered with the `--help` flag.

    $ run-fitly-prod
    
This script will also apply settings found in the module `fitly.prod_settings` (or a custom Python file supplied
with the `--settings` flag) and which takes precedence over the same settings
found in `fitly.settings`.

A notable advantage of using `mod_wsgi` over other WSGI servers is that we do
not need to configure and run a web server separate to the WSGI server. When
using other WSGI servers (such as Gunicorn or uWSGI), you do not want to expose
them directly to web requests from the outside world for two reasons: 1)
incoming requests will not be buffered, exposing you to potential denial of
service attacks, and 2) you will be serving your static assets via Dash's Flask
instance, which is slow. The production script uses `mod_wsgi-express` to spin
up an Apache process (separate to any process already running and listening on
port 80) that will buffer requests, passing them off to the worker processes
running your app, and will also set up the Apache instance to serve your static
assets much faster than would be the case through the Python worker processes.

_Note:_ You will need to reinstall this package in order for changes to the
`run-fitly-prod` script to take effect even if you
installed its an editable install with (ie `pip install -e`).


### Running with a different WSGI Server

You can easily run your app using a WSGI server of your choice (such as Gunicorn
for example) with the `fitly.wsgi` entry point
(defined in `wsgi.py`) like so:

    $ gunicorn fitly.wsgi

_Note:_ if you want to enable Dash's debug mode while running with a WSGI server,
you'll need to export the `DASH_DEBUG` environment variable to `true`. See the
[Dev Tools](https://dash.plot.ly/devtools) section of the Dash Docs for more
details.

### Deploy with docker-compose behind reverse proxy (NGINX)
    version: '3'
    services:
      letsencrypt:
        image: linuxserver/letsencrypt
        container_name: letsencrypt 
        cap_add:
          - NET_ADMIN
        restart: always
        ports:
          - "80:80"
          - "443:443"
        environment:
          - PUID=1000
          - PGID=100
          - TZ=America/New_York
          - EMAIL=<your email>
          - URL=<website.com>
          - SUBDOMAINS=fit # this would give a website like fit.website.com
        volumes:
          - /share/CACHEDEV2_DATA/Container/LetsEncrypt:/config
      fitly:
        build:
          dockerfile: Dockerfile
        container_name: fitly
        restart: always
        depends_on:
          - letsencrypt
        ports:
          - "8050:80"
        environment:
          - MODULE_NAME=src.fitly.app
          - VARIABLE_NAME=server
          - TZ=America/New_York
          - TIMEOUT=1200
          - PUID=1000
          - PGID=100
          - DASH_DEBUG=true
        volumes:
          - /share/CACHEDEV2_DATA/Container/Fitly-Slap:/app/config
          - /share/CACHEDEV2_DATA/Container/LetsEncrypt/keys:/app/keys


### NGINX (subdomain example)
    server {
        listen 443 ssl;
        listen [::]:443 ssl;
    
        server_name fit.*;
    
        include /config/nginx/ssl.conf;
    
        client_max_body_size 0;
    
        # enable for ldap auth, fill in ldap details in ldap.conf
        #include /config/nginx/ldap.conf;
    
        location / {
            # enable the next two lines for http auth
            #auth_basic "Restricted";
            #auth_basic_user_file /config/nginx/.htpasswd;
    
            # enable the next two lines for ldap auth
            #auth_request /auth;
            #error_page 401 =200 /login;
    
            include /config/nginx/proxy.conf;
            resolver 127.0.0.11 valid=30s;
            set $upstream_fitly fitly;
            proxy_pass http://$upstream_fitly:80;
        }
    }

Be sure to navigate to your mounted docker path on the host and create your `config.ini` from the `config.ini.example`  

# Configuring Your App

## Required Data Sources

### Strava
Copy your client key and secret into your config.ini file.

In your strava settings click "My Api Application" and set the autorization callback to **127.0.0.1:8050?strava**. All other fields you can update as you'd like.

## Optional data sources
Some charts will not work unless these data sources are provided, or until new data sources are added that can pull similar data

### Oura
The oura connections is currently required to generate the home page.

In addition to the home page, data points from oura will be use to make performance analytics more accurate. If oura data is not provided, performance analytics will rely on statically defined metrics in the athlete table (i.e. resting heartrate)

Create a developer account at https://cloud.ouraring.com/oauth/applications

Copy your client key and secret into your config.ini file.

Set the redirect URI to: http://127.0.0.1:8050/settings?oura

### Withings
Sign up for a withings developer account here: https://account.withings.com/partner/dashboard_oauth2

In addition to the home page, data points from withings will be use to make performance analytics more accurate. If withings data is not provided, performance analytics will rely on statically defined metrics in the athlete table (i.e. weight)

Set the redirect URI to: http://127.0.0.1:8050/settings?withings

Copy your client key and secret into your config.ini file.

### Stryd
Pull critical power (ftp) from Stryd. Since Stryd does not share their proprietary formula for calculating CP, we just pull the number rather than trying to recalculate it ourselves.

Enter username and password into config.ini file.

### Peloton
Currently only being used to update titles of workouts on strava. Mainly for use with peloton digital app. (i.e record with stryd/wahoo fitness etc. while listening to peloton class on phone/ipad)

Enter username and password into config.ini file.

### Fitbod & Nextcloud
Fitbod allows exporting your data via the mobile app (Log > Settings icon > Export workout data)

Export your fitbod file to a nextcloud location, and provide that nextcloud location in your config.ini for fit.ly to incorporate into the dashboards.

# Dashboard startup
Navigate to http://127.0.0.1:8050/pages/settings

Enter the password from your config.ini [settings] password

Connect account buttons on top left of screen. Each successful authentication should save your tokens to the api_tokens table in your database.

Click the 'Refresh' button to pull data
