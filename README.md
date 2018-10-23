# PiRA-smart-software
Software for PiRa Smart board implementing hardware interface functions.

www.irnas.eu

UNDER ACTIVE DEVELOPMENT!

## Software support for hardware features
 * USB charger BQ24296 I2c
 * Display SSD1306 I2C
 * RFM95 Lora SPI

## Board support package
 * GPIO for power scheduling
 * GPIO for power output

### Power scheduling
TODO

### Application specific features
 1. Capture camera image and check for daylight/minimal light in image (maybe https://github.com/pageauc/pi-timolo)
 2. WiFi connect and hotspot https://github.com/resin-io/resin-wifi-connect
 3. Capture video for some time if sufficient light is available
 4. Measure distance with MB7092XL-MaxSonar-WRMA1
 5. Send data to TheThingsNetwork
 6. Send data over RockBlock Iridium modem
 7. Send images to Azure cloud
 8. Send data to M2X IoT platform

## RESIN - Fleet configuration variables
The following fleet configuration variables must be defined for correct operation:
 * `RESIN_HOST_CONFIG_dtoverlay` to value `pi3-miniuart-bt`
 * `RESIN_HOST_CONFIG_gpu_mem` to value `128`, required by camera
 * `RESIN_HOST_CONFIG_start_x` to value `1`, required by camera
 * `RESIN_SUPERVISOR_DELTA` to value `1`, so updates are faster, optional.

## Supported environment variables

The following environment variables can be used to configure the firmware:

* Global
  * `SLEEP_ENABLE_MODE` (default `sleep`) , options are:
    * `off` - do not sleep
    * `charging` - do not sleep when charging
    * `debug` - sleep even if debug mode is enabled
    * `sleep` - go to sleep when requested
  * `WIFI_ENABLE_MODE` (default `on`) , options are:
    * `on` - always on when device is turned on
    * `charging` - only when charging
    * `debug` - only when debug
    * `off` -  always off
  * `BOOT_DISABLE` (default `0`), boot of this software is disabled if set to `1`
  * `LOOP_DELAY` (default `10`), in seconds, delay of main process loop (how often it is executed)
  * `WIFI_SSID` (default `pira-01`), on non-resin ONLY for now
  * `WIFI_PASSWORD` (default `pirapira`), on non-resin ONLY for now
  * `DEBUG_ENABLE_MODE` (default `none`), read from given pin, can be `gpio:5` where number can be any BCM pin to turn on debug
  * `MODULES` a comma separated list of modules to load, the following is a list of all modules currently available `pira.modules.scheduler,pira.modules.ultrasonic,pira.modules.camera,pira.modules.lora,pira.modules.rockblock,pira.modules.nodewatcher,pira.modules.debug,pira.modules.webserver,pira.modules.m2x_plat,pira.modules.can,pira.modules.azure_images`, delete the ones you do not wish to use.
  * `SHUTDOWN_VOLTAGE` (default `2.6`V) to configure when the system should shutdown. At 2.6V hardware shutdown will occur, suggested value is 2.3-3V. When this is triggered, the device will wake up next based on the configured interval, unless the battery voltage continues to fall under the hardware limit, then it will boot again when it charges. Note this shutdown will be aborted if in debug mode.
  * `LATITUDE` (default `0`) to define location, used for sunrise/sunset calculation
  * `LONGITUDE` (default `0`) to define location
* Pira BLE (can be controled with following values, if set to `None` BLE device settings are not updated): 
  * `PIRA_POWER` (default `None`), p - safety on period, in seconds
  * `PIRA_SLEEP` (default `None`), s - safety off period, in seconds
  * `PIRA_REBOOT` (default `None`), r - reboot period duration, in seconds
  * `PIRA_WAKEUP` (default `None`), w - period for next wakeup, in seconds
* Scheduler
  * `SCHEDULE_MONTHLY` (default `0`), disabled - static schedule is used, enabled if set to `1`
  * `POWER_THRESHOLD_HALF` (default `0`), voltage at which `SCHEDULE_T_OFF` time is doubled, suggested `3.7`
  * `POWER_THRESHOLD_QUART` (default `0`), voltage at which `SCHEDULE_T_OFF` time is quadrupled, suggested `3.4`
  * Static schedule variables:
    * `SCHEDULE_START` (default `00:01`), option is also `sunrise` calculated automatically if lat/long are defined
    * `SCHEDULE_END` (default `23:59`), option is also `sunset`calculated automatically if lat/long are defined
    * `SCHEDULE_T_ON` (default `5`), remains on for specified time in minutes
    * `SCHEDULE_T_OFF` (default `55`), remains off for specified time in minutes
  * Month-dependent schedule variables (`x` is number of desired month):
    * `SCHEDULE_MONTHx_START` (default `08:00`), option is also `sunrise` calculated automatically if lat/long are defined
    * `SCHEDULE_MONTHx_END` (default `18:00`), option is also `sunset`calculated automatically if lat/long are defined
    * `SCHEDULE_MONTHx_T_ON` (default `35`), remains on for specified time in minutes
    * `SCHEDULE_MONTHx_T_OFF` (default `15`), remains off for specified time in minutes
* Camera
  * `CAMERA_RESOLUTION` (default `1280x720`), options are `1280x720`, `1920x1080`, `2592x1952` and some others. Mind fi copying resolution that you use the letter `x` not a multiply character.
  * `CAMERA_VIDEO_DURATION` (default `until-sleep`), duration in minutes or `off`
  * `CAMERA_MIN_LIGHT_LEVEL` (default `0.0`), minimum required for video to start recording
  * `CAMERA_FAIL_SHUTDOWN` (default `0`), can camera shutdown the device for example if not enough light, set to `1` to enable
  * `CAMERA_SNAPSHOT_INTERVAL` (default `off`), duration in minutes to be configured
  * `CAMERA_AZURE` (default `off`), take screenshot on every process 
* Rockblock
  * `ROCKBLOCK_REPORT_INTERVAL` (default `24`), power on interval
  * `ROCKBLOCK_RETRIES` (default `2`), maximum number of retries
* LoRa
  * `LORA_DEVICE_ADDR`
  * `LORA_NWS_KEY`
  * `LORA_APPS_KEY`
  * `LORA_SPREAD_FACTOR` (default `7`)
  * `LORA_REGION` (default `EU`)
* Nodewatcher (to report measurements to Nodewatcher platform)
  * `NODEWATCHER_UUID`
  * `NODEWATCHER_HOST`
  * `NODEWATCHER_KEY`
* Sensors
  * `MCP3021_RATIO` (default `0.0217`) is the conversion value between raw reading and voltage, measure and calibrate for more precise readings
* CAN (MCP2515)
  * `CAN_SPEED` (default `500000`) is the speed of the CAN Bus
  * `CAN_NUM_DEV` (default `4`) number of CAN devices to scan for
  * `CAN_NUM_SEN` (default `16`) number of CAN sensor addresses to scan on each device
* M2X
  * `M2X_KEY` (must have) is the key of your M2X account
  * `M2X_DEVICE_ID` (must have) is the device ID you are connecting to
  * `M2X_NAME` (default `DEMO_PI`) is the name of the set of data
* Azure Images
  * `AZURE_ACCOUNT_NAME` (must have), is the name 
  * `AZURE_ACCOUNT_KEY` (must have), is the account key
  * `AZURE_CONTAINER_NAME` (default `ImageExample`), is the container name in the blob
  * `AZURE_DELETE_LOCAL` (default `off`), if set to `on`, it will delete past files in the /data/camera/ folder
  * `AZURE_DELETE_CLOUD` (default `off`), if set to `on`, it will delete the whole container in cloud

 ### Using without Resin.io
 To use on a standard Raspbian Lite image complete the following steps:
  * Install Raspbian Lite
  * Install git and clone this repo
  * Execute /scripts/raspbian_install.sh (with sudo) and follow the instructions at the end
  * Configure environmental variables by adding them to the end of `/etc/environment` file, for example `SLEEP_WHEN_CHARGING="1"`
  * Run the start script by (-E is required to read environment variables correctly):
  ```
  cd pira-smart-software
  sudo -E ./start.sh
  ```
 ### Using it with Resin.io Local Mode
 To use it with Local Mode (Development) with Resin.io
  * Download resin-cl
  * Rename Dockerfile.template to `Dockerfile`
  * Execute ```sudo ./resin local scan``` to scan the local network
  * To push the firmware ```sudo ./resin local push ID_HERE -s LOCATION```
  
 Extra useful things:
  * Enviroment variables place in: `.resin-sync.yml` like this: 
	```
	environment:
		- AZURE_ACCOUNT_NAME=rpiimages
	```
