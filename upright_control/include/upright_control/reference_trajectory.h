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

#include <ocs2_core/misc/LinearInterpolation.h>
#include <ocs2_core/reference/TargetTrajectories.h>

#include <upright_control/types.h>

namespace upright {

inline Vec3d get_target_position(const VecXd& target) {
    return target.head<3>();
}

inline Quatd get_target_orientation(const VecXd& target) {
    return Quatd(target.segment<4>(3));
}

inline std::pair<VecXd, Quatd> interpolateEndEffectorPose(
    ocs2::scalar_t time, const ocs2::TargetTrajectories& targetTrajectories) {
    const auto& timeTrajectory = targetTrajectories.timeTrajectory;
    const auto& stateTrajectory = targetTrajectories.stateTrajectory;

    VecXd position;
    Quatd orientation;

    if (stateTrajectory.size() > 1) {
        // Normal interpolation case
        int index;
        ocs2::scalar_t alpha;
        std::tie(index, alpha) =
            ocs2::LinearInterpolation::timeSegment(time, timeTrajectory);

        const auto& lhs = stateTrajectory[index];
        const auto& rhs = stateTrajectory[index + 1];
        const Quatd q_lhs = get_target_orientation(lhs);
        const Quatd q_rhs = get_target_orientation(rhs);

        position = alpha * get_target_position(lhs) +
                   (1.0 - alpha) * get_target_position(rhs);
        orientation = q_lhs.slerp((1.0 - alpha), q_rhs);
    } else {  // stateTrajectory.size() == 1
        position = get_target_position(stateTrajectory.front());
        orientation = get_target_orientation(stateTrajectory.front());
    }

    return {position, orientation};
}

}  // namespace upright
