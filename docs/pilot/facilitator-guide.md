# Facilitator guide: two-team Incident Atlas pilot

**State:** ready to run; not yet conducted with external participants. The local rehearsal uses synthetic data and synthetic identities. Do not write rehearsal observations as participant findings.

## Goal

Compare each team's current incident-investigation workflow with Incident Atlas on two equivalent, controlled latency-after-deploy exercises. Observe whether the timeline, signal visibility, uncertainty labels, and source citations help produce a defensible handoff. This is a usability exercise, not an incident-accuracy benchmark.

## Participants and roles

Invite one responder pair from each of two teams only after the project owner authorizes outreach and the pilot data agreement is accepted. Give each group its own workspace, viewer/editor roles, and service owner. Do not provision a participant until the authorized OIDC subject is known and approved. Record role changes in the audit trail.

## Counterbalanced schedule

Use four sessions if staffing allows. Randomly assign workflow order within each team and rotate the scenario mapping:

| Session | First method | Second method | Scenario order |
|---|---|---|---|
| Team A | Usual workflow | Incident Atlas | Checkout, then catalog |
| Team B | Incident Atlas | Usual workflow | Catalog, then checkout |
| Team A repeat / Team B repeat | Swap first method | Swap second method | Reverse each team's scenario order |

If only one session per team is feasible, randomize which team starts with Incident Atlas and use the opposite scenario order. Capture the assignment method before sessions begin. Allow a short reset between methods and do not disclose the expected cause label.

## Facilitation steps

1. Read the participant instructions verbatim. Explain that all telemetry and deploy events are synthetic, there is no production connection, and mitigation controls are simulation-only.
2. Start the assigned scenario and timer at the same discovery cue for both methods. Give the same symptom statement and evidence access window.
3. Do not guide investigation choices. Ask participants to say when they have enough evidence to state a hypothesis and to identify what remains uncertain.
4. Stop the first timer at the participant's first useful evidence, and the second when they present a defensible hypothesis with supporting sources. Record both times in seconds.
5. Score citation quality from the results template: correct captured source, resolves to the snapshot, and is relevant to the claim. Record unsupported claims separately; do not infer intent.
6. Ask the same friction questions after both methods. Record quotes only with consent; use participant IDs rather than names.
7. Reset database evidence and the sample service before the next assignment. Preserve only the anonymized results sheet according to the approved retention policy.
8. Record whether the session was rehearsal or an actual participant session, scenario/order assignment, build commit, and any deviation.

## Safety and stopping conditions

Stop if a credential, personal/customer data, real deployment target, unexpected network connection, or non-synthetic telemetry appears. Do not accept a request to execute a mitigation; the pilot has no execution pathway. Pause participant testing if workspace isolation or identity behavior differs from the documented role matrix.

## Report interpretation

Report each team's paired comparison and the individual observations. Keep measured participant results separate from synthetic regression scores and local rehearsal timings. Do not claim adoption, time savings, reliability, or causality from one or two sessions. A proposed product change must cite the observed friction and identify whether it is a participant finding or an internal facilitator observation.
