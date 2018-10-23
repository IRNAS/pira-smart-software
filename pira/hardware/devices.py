"""Hardware device definitions."""

# GPIO pins (BCM).
GPIO_PIRA_STATUS_PIN = 17
GPIO_SOFT_POWER_PIN = 25


# These devices must go to soft uart
# Rockblock modem
# ROCKBLOCK_UART = '/dev/ttyAMA0'
# Plantower
# PLANTOWER_UART = '/dev/ttyAMA0'
PIRASMART_UART = '/dev/ttyAMA0' #if pi3-miniuart-bt overlay
#PIRASMART_UART = '/dev/ttyS0' #default

# Ultrasonic sensor.
GPIO_ULTRASONIC_RX_PIN = 5

# Lora modem.
GPIO_LORA_RESET_PIN = 13
GPIO_LORA_DIO_0_PIN = 12
GPIO_LORA_DIO_1_PIN = 1
GPIO_LORA_DIO_2_PIN = 7
