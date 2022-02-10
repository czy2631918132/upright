import os

import numpy as np
import rospkg

from tray_balance_sim import geometry
import tray_balance_ocs2.MobileManipulatorPythonInterface as ocs2

import IPython


LIBRARY_PATH = "/tmp/ocs2"


class TaskSettingsWrapper:
    def __init__(self, composites, x0):
        settings = ocs2.TaskSettings()

        settings.method = ocs2.TaskSettings.Method.DDP
        settings.initial_state = x0

        # tray balance settings
        settings.tray_balance_settings.enabled = True
        settings.tray_balance_settings.robust = False
        settings.tray_balance_settings.constraint_type = ocs2.ConstraintType.Soft
        settings.tray_balance_settings.mu = 1e-2
        settings.tray_balance_settings.delta = 1e-3

        config = ocs2.TrayBalanceConfiguration()
        config.objects = composites
        settings.tray_balance_settings.config = config

        # robust settings
        robust_params = ocs2.RobustParameterSet()
        robust_params.min_support_dist = 0.04
        robust_params.min_mu = 0.5
        robust_params.min_r_tau = geometry.circle_r_tau(robust_params.min_support_dist)
        settings.tray_balance_settings.robust_params = robust_params

        # collision avoidance settings
        settings.collision_avoidance_settings.enabled = False
        settings.collision_avoidance_settings.collision_link_pairs = [
            ("forearm_collision_link_0", "balanced_object_collision_link_0")
        ]
        settings.collision_avoidance_settings.minimum_distance = 0

        # dynamic obstacle settings
        settings.dynamic_obstacle_settings.enabled = True
        settings.dynamic_obstacle_settings.obstacle_radius = 0.1

        for sphere in [
            ocs2.CollisionSphere(
                name="elbow_collision_link",
                parent_frame_name="elbow_collision_joint",
                offset=np.zeros(3),
                radius=0.15,
            ),
            ocs2.CollisionSphere(
                name="forearm_collision_sphere_link1",
                parent_frame_name="forearm_collision_sphere_joint1",
                offset=np.zeros(3),
                radius=0.15,
            ),
            ocs2.CollisionSphere(
                name="forearm_collision_sphere_link2",
                parent_frame_name="forearm_collision_sphere_joint2",
                offset=np.zeros(3),
                radius=0.15,
            ),
            ocs2.CollisionSphere(
                name="wrist_collision_link",
                parent_frame_name="wrist_collision_joint",
                offset=np.zeros(3),
                radius=0.15,
            ),
        ]:
            settings.dynamic_obstacle_settings.collision_spheres.push_back(sphere)

        # If we are not using robust constraints, just apply a hard-coded
        # sphere around the balanced objects. If we are robust, this should be
        # added later to correspond to the robust spheres.
        if not settings.tray_balance_settings.robust:
            settings.dynamic_obstacle_settings.collision_spheres.push_back(
                ocs2.CollisionSphere(
                    name="thing_tool_collision_link",
                    parent_frame_name="thing_tool",
                    offset=np.zeros(3),
                    radius=0.25,
                )
            )

        self.settings = settings

    def get_num_balance_constraints(self):
        if self.settings.tray_balance_settings.robust:
            return len(self.settings.tray_balance_settings.robust_params.balls) * 3
        return self.settings.tray_balance_settings.config.num_constraints()

    def get_num_collision_avoidance_constraints(self):
        if self.settings.collision_avoidance_settings.enabled:
            return len(self.settings.collision_avoidance_settings.collision_link_pairs)
        return 0

    def get_num_dynamic_obstacle_constraints(self):
        if self.settings.dynamic_obstacle_settings.enabled:
            return len(self.settings.dynamic_obstacle_settings.collision_spheres)
        return 0


def get_task_info_path():
    rospack = rospkg.RosPack()
    return os.path.join(
        rospack.get_path("tray_balance_ocs2"), "config", "mpc", "task.info"
    )


def make_target_trajectories(target_times, target_states, target_inputs):
    assert len(target_times) == len(target_states)
    assert len(target_times) == len(target_inputs)

    target_times_ocs2 = ocs2.scalar_array()
    for target_time in target_times:
        target_times_ocs2.push_back(target_time)

    target_states_ocs2 = ocs2.vector_array()
    for target_state in target_states:
        target_states_ocs2.push_back(target_state)

    target_inputs_ocs2 = ocs2.vector_array()
    for target_input in target_inputs:
        target_inputs_ocs2.push_back(target_input)

    return ocs2.TargetTrajectories(
        target_times_ocs2, target_states_ocs2, target_inputs_ocs2
    )


def setup_ocs2_mpc_interface(settings, target_times, target_states, target_inputs):
    mpc = ocs2.mpc_interface(get_task_info_path(), LIBRARY_PATH, settings)
    target_trajectories = make_target_trajectories(
        target_times, target_states, target_inputs
    )
    mpc.reset(target_trajectories)
    return mpc
