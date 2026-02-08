# Tasks

## Todo

### Add support for constrained optimization
- **Assignee:** @alice
- **Labels:** feature, optimization

Add equality and inequality constraint support to the trajectory
optimization solver. Should integrate with the existing cost function
interface.

### Improve documentation for getting started guide
- **Labels:** docs

The current getting started guide is missing examples for common
use cases. Add at least 3 worked examples.

## In Progress

### Fix numerical instability in integrator
<!-- id: PVTI_example123 -->
- **Assignee:** @bob
- **Labels:** bug, numerics

The RK4 integrator produces NaN values for stiff systems. Need to
add adaptive step size control.

```julia
# Reproducer
solve(prob, RK4(), dt=0.1)  # NaN after ~50 steps
```

## Done

### Set up CI with Julia nightly
<!-- id: PVTI_example456 -->
- **Assignee:** @charlie

Added GitHub Actions workflow that tests against Julia release and nightly.
