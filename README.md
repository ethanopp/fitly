# Fit.ly
Web analytics for endurance athletes
![Image description](https://i.imgur.com/Z3mfOMR.jpeg)
![Image description](https://i.imgur.com/A5rJNff.png)
![Image description](https://i.imgur.com/PewZiKt.png)
![Image description](https://i.imgur.com/hsSPvyn.png)
![Image description](https://i.imgur.com/26Bglbc.jpg)
![Image description](https://i.imgur.com/tbx5YmT.png)
![Image description](https://i.imgur.com/zeNnCvn.jpg)
![Image description](https://i.imgur.com/7j6Ez9K.jpg)
![Image description](https://i.imgur.com/uafoBFI.jpg)

Special thanks to Slapdash for helping organize!
https://github.com/ned2/slapdash
# Installation Methods
##  Docker (Recommended) 
    docker create --name=fitly \
        --restart unless-stopped \
        -e MODULE_NAME=src.fitly.app \
        -e VARIABLE_NAME=server \
        -e TZ=America/New_York \
        -e TIMEOUT=1200 \
        -e DASH_DEBUG=true \
        -p 8050:80 \
        -v <local mount path>:/app/config \
        ethanopp/fitly:latest
   
## Python IDE
After cloning/downloading the repository, install Fit.ly into your environment:

    $ pip install -e PATH_TO_fitly
    
# Configuring Your App
Edit the `config.ini.example` file on your local mount path with your settings (more information below) and change the name of the file to `config.ini`.

## Required Data Sources

### Strava
Copy your client key and secret into your config.ini file.

In your strava settings (https://www.strava.com/settings/api) set the autorization callback to **127.0.0.1:8050?strava**. All other fields you can update as you'd like.

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

If using Oura, HRV recommendations can be used to auto-bookmark new classes on your peloton device daily. Class types to be bookmarked can be configured on the settings page (i.e. on days where HRV recommendation is "Low" effort, auto bookmark some new "Running" workouts of the class type "Fun Run", "Endurance Run", "Outdoor Fun Run", and "Outdoor Endurance Run")

![Image description](https://i.imgur.com/q654WHY.png)

Enter username and password into config.ini file.

### Fitbod & Nextcloud
Fitbod allows exporting your data via the mobile app (Log > Settings icon > Export workout data)

Export your fitbod file to a nextcloud location, and provide that nextcloud location in your config.ini for fit.ly to incorporate into the dashboards.

### Spotify
The spotify connections is currently required to generate the music page.

Fitly can keep a history of every song you listen to on spotify and analyze your listenind behavior (skipped, fast forwarded, rewound ,etc.) to determine song likeablity. Listening behavior can then be analyzed by activity type and intensity (i.e what music do you listen to during high intensity runs), clustered into music type (K-means cluster on spotify audio features) and playlists can be automatically generated with recommended music for your next recommended workout.

Create a developer account here: https://developer.spotify.com/dashboard/

Set the redirect URI to: http://127.0.0.1:8050/settings?spotify

Copy your client ID and secret into your config.ini file.

# Dashboard startup
Navigate to http://127.0.0.1:8050/pages/settings

Enter the password from your `config.ini` [settings] password

Connect account buttons on top left of screen. Each successful authentication should save your tokens to the api_tokens table in your database.

Click the 'Refresh' button to pull data

### Dashboard startup tips for python IDE users
Installing this package into your virtualenv will result into the development
executable being installed into your path when the virtualenv is activated. This
command invokes your Dash app's `run_server` method, which in turn uses the
Flask development server to run your app. The command is invoked as follows:

    $ run-fitly-dev

The script takes a couple of arguments optional parameters, which you can
discover with the `--help` flag. You may need to set the port using the `--port`
parameter. If you need to expose your app outside your local machine, you will
want to set `--host 0.0.0.0`.

# Hosting your application externally (docker compose with nginx)
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
          - TZ=America/New_York
          - EMAIL=<your email>
          - URL=<website.com>
          - SUBDOMAINS=fit # this would give a website like fit.website.com
        volumes:
          - <host config dir>:/config
      fitly:
        image: ethanopp/fitly:latest
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
