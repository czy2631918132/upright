import rospy
import numpy as np
import tray_balance_ocs2 as ctrl
from upright_ros_interface import TrajectoryClient

from trajectory_msgs.msg import JointTrajectory
from ocs2_msgs.msg import (
    mpc_flattened_controller,
    mpc_observation,
    mpc_state,
    mpc_input,
)
from ocs2_msgs.srv import reset as mpc_reset
from ocs2_msgs.srv import resetRequest as mpc_reset_request


# TODO: ideally, we'd fold this into the C++ MPC node for performance and
# elegance

class ROSRealInterface:
    """Interface between the MPC node and the simulation."""

    def __init__(self, topic_prefix, ctrl_name):
        rospy.init_node("real_interface")  # TODO better name

        # client for interfacing with the real robot
        self.client = TrajectoryClient(ctrl_name)

        # subscribe to trajectory generated by the MPC
        self.trajectory_sub = rospy.Subscriber(
            topic_prefix + "_joint_trajectory", JointTrajectory, self._trajectory_cb
        )

        # publish an observation to the MPC
        self.observation_pub = rospy.Publisher(
            topic_prefix + "_mpc_observation", mpc_observation, queue_size=1
        )

        # wait for everything to be setup
        rospy.sleep(1.0)

    def reset_mpc(self, ref):
        # call service to reset, repeating until done
        srv_name = "mobile_manipulator_mpc_reset"

        print("Waiting for MPC reset service...")

        rospy.wait_for_service(srv_name)
        mpc_reset_service = rospy.ServiceProxy(srv_name, mpc_reset)

        req = mpc_reset_request()
        req.reset = True
        req.targetTrajectories.timeTrajectory = ref.ts
        for x in ref.xs:
            msg = mpc_state()
            msg.value = x
            req.targetTrajectories.stateTrajectory.append(msg)
        for u in ref.us:
            msg = mpc_input()
            msg.value = u
            req.targetTrajectories.inputTrajectory.append(msg)

        try:
            resp = mpc_reset_service(req)
        except rospy.ServiceException as e:
            print("MPC reset failed.")
            print(e)
            return 1

        print("MPC reset done.")

    def publish_observation(self, t, x, u):
        msg = mpc_observation()
        msg.time = t
        msg.state.value = x
        msg.input.value = u
        self.observation_pub.publish(msg)

    def _feedback_cb(self, msg):
        # msg is FollowJointTrajectoryActionFeedback
        q = msg.feedback.actual.positions
        v = msg.feedback.actual.velocities

        # we don't get actual feedback on the accelerations, so we assume it is
        # tracking desired
        a = msg.feedback.desired.accelerations

        t = msg.header.stamp.to_sec()  # TODO I guess we'll use walltime?
        x = np.concatenate((q, v, a))
        u = []  # I think we don't need to care about this; it isn't used
        self.publish_observation(t, x, u)

    def _trajectory_cb(self, msg):
        self.client.send_joint_trajectory(msg, self._feedback_cb)
