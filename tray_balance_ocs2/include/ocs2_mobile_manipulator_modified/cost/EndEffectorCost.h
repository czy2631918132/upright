/******************************************************************************
Copyright (c) 2020, Farbod Farshidian. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

 * Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

 * Neither the name of the copyright holder nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
******************************************************************************/

#pragma once

#include <memory>

#include <ocs2_mobile_manipulator_modified/definitions.h>
#include <ocs2_pinocchio_interface/PinocchioEndEffectorKinematics.h>
#include <ocs2_robotic_tools/end_effector/EndEffectorKinematics.h>

#include <ocs2_core/cost/StateCost.h>
#include <ocs2_oc/synchronized_module/ReferenceManager.h>

namespace ocs2 {
namespace mobile_manipulator {

class EndEffectorCost final : public StateCost {
   public:
    using vector3_t = Eigen::Matrix<scalar_t, 3, 1>;
    using quaternion_t = Eigen::Quaternion<scalar_t>;

    EndEffectorCost(
        const matrix_t W,  // note not reference
        const EndEffectorKinematics<scalar_t>& endEffectorKinematics,
        const ReferenceManager& referenceManager)
        : W_(std::move(W)),
          endEffectorKinematicsPtr_(endEffectorKinematics.clone()),
          referenceManagerPtr_(&referenceManager) {
        if (endEffectorKinematics.getIds().size() != 1) {
            throw std::runtime_error(
                "[EndEffectorConstraint] endEffectorKinematics has wrong "
                "number of "
                "end effector IDs.");
        }
        pinocchioEEKinPtr_ = dynamic_cast<PinocchioEndEffectorKinematics*>(
            endEffectorKinematicsPtr_.get());
    }

    ~EndEffectorCost() override = default;

    EndEffectorCost* clone() const override {
        return new EndEffectorCost(W_, *endEffectorKinematicsPtr_,
                                   *referenceManagerPtr_);
    }

    scalar_t getValue(scalar_t time, const vector_t& state,
                      const TargetTrajectories& targetTrajectories,
                      const PreComputation& preComp) const override {
        const auto desiredPositionOrientation =
            interpolateEndEffectorPose(time);

        vector_t err = vector_t::Zero(6);
        err.head<3>() = endEffectorKinematicsPtr_->getPosition(state).front() -
                        desiredPositionOrientation.first;
        err.tail<3>() = endEffectorKinematicsPtr_
                            ->getOrientationError(
                                state, {desiredPositionOrientation.second})
                            .front();
        return 0.5 * err.transpose() * W_ * err;
    }

    ScalarFunctionQuadraticApproximation getQuadraticApproximation(
        scalar_t time, const vector_t& state,
        const TargetTrajectories& targetTrajectories,
        const PreComputation& preComp) const override {
        const auto desiredPositionOrientation =
            interpolateEndEffectorPose(time);

        // NOTE: input is not used in this state cost, so we give it a
        // dimension of zero.
        auto approximation =
            ScalarFunctionQuadraticApproximation(state.rows(), 0);
        approximation.setZero(state.rows(), 0);

        // Linear approximations of position and orientation error
        const auto eePosition =
            endEffectorKinematicsPtr_->getPositionLinearApproximation(state)
                .front();
        const auto eeOrientationError =
            endEffectorKinematicsPtr_
                ->getOrientationErrorLinearApproximation(
                    state, {desiredPositionOrientation.second})
                .front();

        // std::cout << "EE orientation error = " << eeOrientationError.f << std::endl;

        // Function value
        vector_t e = vector_t::Zero(6);
        e << eePosition.f - desiredPositionOrientation.first,
            eeOrientationError.f;
        approximation.f = 0.5 * e.transpose() * W_ * e;

        // Jacobian
        matrix_t dedx(6, state.rows());
        dedx.setZero();
        dedx << eePosition.dfdx, eeOrientationError.dfdx;
        approximation.dfdx = e.transpose() * W_ * dedx;

        // Hessian (Gauss-Newton approximation)
        approximation.dfdxx = dedx.transpose() * W_ * dedx;

        return approximation;
    }

   private:
    EndEffectorCost(const EndEffectorCost& other) = default;

    std::pair<vector_t, quaternion_t> interpolateEndEffectorPose(
        scalar_t time) const {
        const auto& targetTrajectories =
            referenceManagerPtr_->getTargetTrajectories();
        const auto& timeTrajectory = targetTrajectories.timeTrajectory;
        const auto& stateTrajectory = targetTrajectories.stateTrajectory;

        vector_t position;
        quaternion_t orientation;

        if (stateTrajectory.size() > 1) {
            // Normal interpolation case
            int index;
            scalar_t alpha;
            std::tie(index, alpha) =
                LinearInterpolation::timeSegment(time, timeTrajectory);

            const auto& lhs = stateTrajectory[index];
            const auto& rhs = stateTrajectory[index + 1];
            const quaternion_t q_lhs(lhs.tail<4>());
            const quaternion_t q_rhs(rhs.tail<4>());

            position = alpha * lhs.head<3>() + (1.0 - alpha) * rhs.head<3>();
            orientation = q_lhs.slerp((1.0 - alpha), q_rhs);
        } else {  // stateTrajectory.size() == 1
            position = stateTrajectory.front().head<3>();
            orientation = quaternion_t(stateTrajectory.front().tail<4>());
        }

        return {position, orientation};
    }

    matrix_t W_;  // weight matrix

    /** Cached pointer to the pinocchio end effector kinematics. Is set to
     * nullptr if not used. */
    PinocchioEndEffectorKinematics* pinocchioEEKinPtr_ = nullptr;

    vector3_t eeDesiredPosition_;
    quaternion_t eeDesiredOrientation_;
    std::unique_ptr<EndEffectorKinematics<scalar_t>> endEffectorKinematicsPtr_;
    const ReferenceManager* referenceManagerPtr_;
};

}  // namespace mobile_manipulator
}  // namespace ocs2
