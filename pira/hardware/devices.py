"""Hardware device definitions."""
import os

# GPIO pins (BCM).
GPIO_SOFT_POWER_PIN = 25

#GPIO_PIRA_STATUS_PIN: 17 for PiraSmart v1_0, 10 for 10 PiraSmart v2_1
env_status_pin =  os.environ.get('PIRA_SMART_STATUS_PIN', '17')
try:
    GPIO_PIRA_STATUS_PIN =  int(env_status_pin)
except:
    GPIO_PIRA_STATUS_PIN = 17   # PiraSmart v1_0

# These devices must go to soft uart
# Rockblock modem
# ROCKBLOCK_UART = '/dev/ttyAMA0'
# Plantower
# PLANTOWER_UART = '/dev/ttyAMA0'
# PIRASMART_UART = '/dev/ttyAMA0' #if pi3-miniuart-bt overlay
PIRASMART_UART = '/dev/ttyS0' #default

# Ultrasonic sensor.
GPIO_ULTRASONIC_RX_PIN = 5

# Lora modem.
GPIO_LORA_RESET_PIN = 13
GPIO_LORA_DIO_0_PIN = 12
GPIO_LORA_DIO_1_PIN = 1
GPIO_LORA_DIO_2_PIN = 7
