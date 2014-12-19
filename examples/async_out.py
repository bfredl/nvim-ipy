from time import sleep
import sys
sleep(1)
for i in range(10):
    sleep(0.3)
    print(i)
    sys.stdout.flush()
