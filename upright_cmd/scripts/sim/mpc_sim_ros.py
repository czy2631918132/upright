#!/usr/bin/env python3
"""Closed-loop upright simulation using Pybullet over ROS."""
import time
import datetime

import rospy
import numpy as np
from pyb_utils.ghost import GhostSphere
from pyb_utils.frame import debug_frame_world

from upright_sim import simulation
from upright_core.logging import DataLogger, DataPlotter
import upright_core as core
import upright_control as ctrl
import upright_cmd as cmd

from mobile_manipulation_central import (
    SimulatedUR10ROSInterface,
    SimulatedMobileManipulatorROSInterface,
    SimulatedViconObjectInterface,
)

import IPython


def main():
    np.set_printoptions(precision=3, suppress=True)

    cli_args = cmd.cli.sim_arg_parser().parse_args()

    # load configuration
    config = core.parsing.load_config(cli_args.config)
    sim_config = config["simulation"]
    ctrl_config = config["controller"]
    log_config = config["logging"]

    # start the simulation
    timestamp = datetime.datetime.now()
    sim = simulation.BulletSimulation(
        config=sim_config, timestamp=timestamp, cli_args=cli_args
    )

    # settle sim to make sure everything is touching comfortably
    sim.settle(5.0)

    # initial time, state, input
    t = 0.0
    q, v = sim.robot.joint_states()
    a = np.zeros(sim.robot.nv)
    x_obs = sim.dynamic_obstacle_state()
    x = np.concatenate((q, v, a, x_obs))
    u = np.zeros(sim.robot.nu)

    Q_obs = np.array([0, 0, 0, 1])

    # data logging
    logger = DataLogger(config)

    logger.add("sim_timestep", sim.timestep)
    logger.add("duration", sim.duration)
    logger.add("object_names", [str(name) for name in sim.objects.keys()])

    logger.add("nq", ctrl_config["robot"]["dims"]["q"])
    logger.add("nv", ctrl_config["robot"]["dims"]["v"])
    logger.add("nx", ctrl_config["robot"]["dims"]["x"])
    logger.add("nu", ctrl_config["robot"]["dims"]["u"])

    model = ctrl.manager.ControllerModel.from_config(ctrl_config, x0=x)

    # reference pose trajectory
    model.update(x=model.settings.initial_state)
    r_ew_w, Q_we = model.robot.link_pose()
    ref = ctrl.wrappers.TargetTrajectories.from_config(ctrl_config, r_ew_w, Q_we, u)

    # frames and ghost (i.e., pure visual) objects
    for r_ew_w_d, Q_we_d in ref.poses():
        debug_frame_world(0.2, list(r_ew_w_d), orientation=Q_we_d, line_width=3)

    # setup the ROS interface
    rospy.init_node("mpc_sim_ros")
    if model.settings.robot_base_type == ctrl.bindings.RobotBaseType.Fixed:
        ros_interface = SimulatedUR10ROSInterface()
    elif model.settings.robot_base_type == ctrl.bindings.RobotBaseType.Omnidirectional:
        ros_interface = SimulatedMobileManipulatorROSInterface()
    else:
        raise ValueError("Unsupported robot base type.")
    if len(sim.dynamic_obstacles) > 0:
        projectile_ros_interface = SimulatedViconObjectInterface("Projectile")
    ros_interface.publish_time(t)

    # wait until a command has been received
    # note that we use real time here since this sim directly controls sim time
    print("Waiting for a command to be received...")
    while not ros_interface.ready():
        ros_interface.publish_feedback(t, q, v)
        ros_interface.publish_time(t)
        t += sim.timestep
        time.sleep(sim.timestep)
        if rospy.is_shutdown():
            return

    print("Command received. Executing...")
    t0 = t

    # add dynamic obstacles and start them moving
    sim.launch_dynamic_obstacles(t0=t0)

    # simulation loop
    while not rospy.is_shutdown() and t - t0 <= sim.duration:
        # feedback is in the world frame
        v_prev = v
        q, v = sim.robot.joint_states(add_noise=True, bodyframe=False)
        ros_interface.publish_feedback(t, q, v)

        # publish feedback on dynamic obstacles if using
        if len(sim.dynamic_obstacles) > 0:
            x_obs = sim.dynamic_obstacle_state()
            r_obs = x_obs[:3]
            projectile_ros_interface.publish_pose(t, r_obs, Q_obs)

        # commands are always in the body frame (to match the real robot)
        sim.robot.command_velocity(ros_interface.cmd_vel, bodyframe=True)

        if logger.ready(t):
            # NOTE: we can try to approximate acceleration using finite
            # differences, but it is extremely inaccurate
            # a = (v - v_prev) / sim.timestep
            x = np.concatenate((q, v, a, x_obs))

            # log sim stuff
            r_ew_w, Q_we = sim.robot.link_pose()
            v_ew_w, ω_ew_w = sim.robot.link_velocity()
            r_ow_ws, Q_wos = sim.object_poses()
            logger.append("ts", t - t0)
            logger.append("xs", x)
            logger.append("r_ew_ws", r_ew_w)
            logger.append("Q_wes", Q_we)
            logger.append("v_ew_ws", v_ew_w)
            logger.append("ω_ew_ws", ω_ew_w)
            logger.append("cmd_vels", ros_interface.cmd_vel)
            logger.append("r_ow_ws", r_ow_ws)
            logger.append("Q_wos", Q_wos)

            # log controller stuff
            r_ew_w_d, Q_we_d = ref.get_desired_pose(t)
            logger.append("r_ew_w_ds", r_ew_w_d)
            logger.append("Q_we_ds", Q_we_d)

            # NOTE: not accurate due to lack of acceleration info
            model.update(x)
            logger.append("ddC_we_norm", model.ddC_we_norm())
            logger.append("balancing_constraints", model.balancing_constraints())
            logger.append("sa_dists", model.support_area_distances())
            logger.append("orn_err", model.angle_between_acc_and_normal())

        t = sim.step(t, step_robot=False)
        ros_interface.publish_time(t)

    try:
        print(f"Min constraint value = {np.min(logger.data['balancing_constraints'])}")
    except:
        pass

    # save logged data
    if cli_args.log is not None:
        logger.save(timestamp, name=cli_args.log)

    if sim.video_manager.save:
        print(f"Saved video to {sim.video_manager.path}")

    # visualize data
    DataPlotter.from_logger(logger).plot_all(show=True)


if __name__ == "__main__":
    main()
