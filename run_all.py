#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Запуск робота + веб-интерфейс. sudo python3 run_all.py"""

import threading
import time

def run_web():
    from web_app import run_web
    run_web(port=5000)

def run_robot():
    from robot_main import Robot
    from web_app import set_robot
    robot = Robot()
    set_robot(robot)
    robot.run()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    time.sleep(1)
    print("Веб: http://localhost:5000")
    run_robot()
