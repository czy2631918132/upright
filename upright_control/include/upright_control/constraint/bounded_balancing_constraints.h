#pragma once

#include <ocs2_core/constraint/StateInputConstraintCppAd.h>
#include <ocs2_pinocchio_interface/PinocchioEndEffectorKinematicsCppAd.h>

#include <upright_core/bounded.h>
#include <upright_core/contact.h>
#include <upright_control/constraint/constraint_type.h>
#include <upright_control/dynamics/dimensions.h>
#include <upright_control/types.h>

namespace upright {

struct BalancingSettings {
    bool enabled = false;
    BalanceConstraintsEnabled constraints_enabled;
    std::map<std::string, BoundedBalancedObject<ocs2::scalar_t>> objects;
    std::vector<ContactPoint<ocs2::scalar_t>> contacts;

    ConstraintType constraint_type = ConstraintType::Soft;
    ocs2::scalar_t mu = 1e-2;
    ocs2::scalar_t delta = 1e-3;
};

std::ostream& operator<<(std::ostream& out,
                         const BalancingSettings& settings);

class BoundedBalancingConstraints final
    : public ocs2::StateInputConstraintCppAd {
   public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    BoundedBalancingConstraints(
        const ocs2::PinocchioEndEffectorKinematicsCppAd& pinocchioEEKinematics,
        const BalancingSettings& settings, const Vec3d& gravity,
        const RobotDimensions& dims, bool recompileLibraries);

    BoundedBalancingConstraints* clone() const override {
        // Always pass recompileLibraries = false to avoid recompiling the same
        // library just because this object is cloned.
        return new BoundedBalancingConstraints(*pinocchioEEKinPtr_, settings_,
                                               gravity_, dims_, false);
    }

    size_t getNumConstraints(ocs2::scalar_t time) const override {
        return num_constraints_;
    }

    size_t getNumConstraints() const { return getNumConstraints(0); }

    VecXd getParameters(ocs2::scalar_t time) const override {
        // Parameters are constant for now
        return VecXd(0);
    }

   protected:
    VecXad constraintFunction(ocs2::ad_scalar_t time, const VecXad& state,
                             const VecXad& input,
                             const VecXad& parameters) const override;

   private:
    BoundedBalancingConstraints(const BoundedBalancingConstraints& other) =
        default;

    std::unique_ptr<ocs2::PinocchioEndEffectorKinematicsCppAd>
        pinocchioEEKinPtr_;
    BalancingSettings settings_;
    RobotDimensions dims_;
    Vec3d gravity_;
    size_t num_constraints_;
};

}  // namespace upright
