import os
import signal
import subprocess

from supervisor import childutils

### This script will clear out temp and encrypted IB log locations before restarting the container, when Supervisor gets a stopped state from IB

# Taken from here: https://stackoverflow.com/questions/28175011/supervisor-docker-how-to-exit-supervisor-if-a-service-doesnt-start
def main():
    while True:
        headers, payload = childutils.listener.wait()
        childutils.listener.ok()
        if headers['eventname'] != 'PROCESS_STATE_FATAL':
            continue
        print("Clearing out temp space")
        subprocess.run(["tmpreaper", "--all", "--showdeleted", "--force", "1h", "/tmp"], capture_output=True)
        print("Emptying log directories")
        subprocess.run(["find", "./myfolder", "-mindepth", "1", "!", "-regex", "'^/root/Jts/ibgateway\(/.*\)?'", "-delete"], capture_output=True)
        print("Killing supervisor")
        os.kill(os.getppid(), signal.SIGTERM)


if __name__ == "__main__":
    main()
