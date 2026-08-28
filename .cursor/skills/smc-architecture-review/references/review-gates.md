# Architecture Review Gates

## A1 Problem Necessity
Is the proposed architectural change solving a demonstrated problem rather than a speculative future need?

## A2 Existing Capability / Reuse
Can an existing Production Owner or contract satisfy the need without creating a parallel owner?

## A3 Alternatives
Are at least the material alternatives recorded, including why the chosen option wins and when rejected options should be revisited?

## A4 Ownership / Boundary
Does every target Capability have one Production Owner? Are control/data/trust boundaries enforceable and non-bypassable where relevant?

## A5 Dependencies / Cascading Effects
Are hard dependencies, ordering constraints and second-order effects explicit enough to drive a Roadmap DAG?

## A6 Security / Operability
Are security, failure recovery, observability and operational ownership covered where they are architecture-changing?

## A7 Pre-mortem / Kill Criteria
Does the decision state how it is most likely to fail and what evidence would trigger rollback/revisit?

## A8 Roadmap Decomposability
Can the target be split into outcome stages with stable boundaries, without embedding exact files/Todos into Architecture?
