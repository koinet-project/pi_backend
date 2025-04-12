# Koinet Raspberry PI Backend

Python backend for the Raspberry PI to create backend for captive portal & admin web.
Consist of several files with separate function:
* `main.py` is the backend file that runs FAST API server. The server updates firebase database, communicate with captive portal and Mikrotik.
* `coinreq.py` script that start the coin acceptor and give update whenever there's coin inputted or user timeout.
* `devicestats.py` script that communicate with Power Sensor & Battery and returns charging status, battery status, and solar panel status.


## How to run

To run & install packages required do this:
1. (Optional) Create a .venv to create a custom environment for python specifically for this project.
2. cd to src folder
3. Install required packages by running `pip install -r requirements.txt`
4. Run the backend by running `python main.py`
5. Now the server is running locally. To run it publicly, use [TryCloudflare](https://try.cloudflare.com/).

## TO-DOs

1. Setup a domain and expose the API through the domain. ex:"https://API.koinet.com"
2. Rate limiting to prevent slowdown or crashing on the PI. Possible problems:
   * Admin abusing refresh that slowdowns other function like user login.
   * User on the captive portal keep refreshing the page, which will create new websocket connection.





