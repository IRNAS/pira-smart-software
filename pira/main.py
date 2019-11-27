# from .boot import Boot
from .boot_stripped import Boot

if __name__ == '__main__':
    boot = Boot()
    boot.boot()
