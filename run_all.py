#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Запуск робота + веб-интерфейс. sudo python3 run_all.py"""

def run_robot():
    from robot_main import Robot
    from web_app import set_robot
    robot = Robot(start_web=True)
    set_robot(robot)
    robot.run()

if __name__ == "__main__":
    run_robot()
