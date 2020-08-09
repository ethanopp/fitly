# Fit.ly
This repo is a fork from https://github.com/ethanopp/fitly

Web analytics for endurance athletes
![Image description](https://imgur.com/HoxtkJm.png)
![Image description](https://imgur.com/jWK6F0O.png)
![Image description](https://imgur.com/oX1Z1iO.png)
![Image description](https://imgur.com/aRu7Pt1.png)
![Image description](https://imgur.com/9dKmnrj.png)

Special thanks to Slapdash for helping organize!
https://github.com/ned2/slapdash

##  Docker Installation (Easiest Method)
These instructions use example directories on my local machine, be sure to update them to your machines directories!
1. Download/Install Docker Desktop (default installation settings) https://www.docker.com/products/docker-desktop 
2. Download the fit.ly files and unzip them somewhere on your local machine https://github.com/ethanopp/fitly/archive/master.zip
3. Run docker desktop, open a command prompt (windows) or terminal (mac)
4. In the cmd/terminal, navigate to the path you saved the fit.ly files which has the `Dockerfile` 
in it. (ex. `cd C:\Users\Ethan\Desktop\fitly-master`)
5. Run the following command to build the image that you will create the docker container (virtual environment) from:
`docker build -t fitly .`
6. Create your docker container:
    ``` 
    docker create --name=fitly \
        --restart unless-stopped \
        -e MODULE_NAME=src.fitly.app \
        -e VARIABLE_NAME=server \
        -e TZ=America/New_York \
        -e TIMEOUT=1200 \
        -e DASH_DEBUG=true \
        -p 8050:80 \
        -v C:\Users\eoppenheim\Desktop\fitly-master\config:/app/config \
        fitly
    ```
7. Edit the `config.ini.example` file on your local machine with your settings (more information below) and change the name of the file to `config.ini`
8. Open the docker desktop dashboard, run your container (play button at top right), open a browser to go to http://127.0.0.1:8050/settings, and enter the password from your `config.ini` [settings] password variable
## Installation (Python IDE)


After cloning/downloading the repository, simply install Fit.ly as a package into your target virtual environment:

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
          - <host config dir>:/config
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
          - <host config dir>:/app/config
          - <path to letsencrypt host config dir>/keys:/app/keys


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
Fitly does not pull workout data directly from peloton, strava is the main hub for our workout data (so sync peloton directly to strava).

For those working out to peloton classes, but not necessarily recording their data via the peloton device (using stryd pod on tread, using wahoo fitness trainer with peloton digital app, etc.), fitly will match workouts started around the same time to workouts published to strava, and update the titles of the strava workout with the peloton class name.

If using Oura, HRV recommendations can be used to auto-bookmark new classes on your peloton device daily. Class types to be bookmarked can be configured on the settings page (i.e. on days where HRV recommendation is "Low" effort, auto bookmark some new "Running" workouts of the class type "Fun Run", "Endurance Run", "Ourdoor Fun Run", and "Ourdoor Endurance Run")

![Image description](https://i.imgur.com/q654WHY.png)

Enter username and password into config.ini file.

### Fitbod & Nextcloud
Fitbod allows exporting your data via the mobile app (Log > Settings icon > Export workout data)

Export your fitbod file to a nextcloud location, and provide that nextcloud location in your config.ini for fit.ly to incorporate into the dashboards.

# Dashboard startup
Navigate to http://127.0.0.1:8050/pages/settings

Enter the password from your config.ini [settings] password

Connect account buttons on top left of screen. Each successful authentication should save your tokens to the api_tokens table in your database.

Click the 'Refresh' button to pull data
