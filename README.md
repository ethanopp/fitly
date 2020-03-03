# fitly
Self hosted web analytics for endurance athletes. This project started out as an app to serve my own personal fitness needs, and after several friends ask that I share the code, it is now in the process of being cleaned up for public use. Please contribute!

Screenshots of the current state dashboards:
![Image description](https://i.imgur.com/CENhmnq.png)
![Image description](https://i.imgur.com/sWtC3aJ.png)
![Image description](https://i.imgur.com/fox1PBV.png)
![Image description](https://i.imgur.com/4Td0RuG.png)
![Image description](https://i.imgur.com/8HsX8KQ.png)
**This repo is still currently under development. Not all functionality will work for everyone yet as we are still cleaning base code.**

# Strava
Copy your client key and secret into your config.ini file.

In your strava settings click "My Api Application" and set the autorization callback to **127.0.0.1:8050**. All other fields you can update as you'd like.

# Oura
Create a developer account at https://cloud.ouraring.com/oauth/applications

Copy your client key and secret into your config.ini file.

Set the redirect URI to: http://127.0.0.1:8050/pages/authorize/oura

# Withings
Sign up for a withings developer account here: https://account.withings.com/partner/dashboard_oauth2

Copy your client key and secret into your config.ini file.

# Dashboard startup
Navigate to http://127.0.0.1:8050/pages/settings

Enter the password from your config.ini [settings] password

Connect account buttons on top left of screen. Each successful authentication should save your tokens to the api_tokens table in your database.

Click the 'Refresh' button to pull data
