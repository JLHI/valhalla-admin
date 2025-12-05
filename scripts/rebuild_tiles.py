#!/usr/bin/env python3
import subprocess
print("Rebuilding tiles...")
subprocess.run(["valhalla_build_tiles","/data/valhalla.json"], check=True)
