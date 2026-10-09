# Visual high-rise criteria

## Candidate cues

- **Strong cast shadow:** a long, coherent shadow that originates at a roof edge and is materially larger/darker than shadows of nearby low-rise buildings.
- **Distinct building entity:** a separable roof and/or visibly connected building body or facade. Trace the physical built form, not a detached dark cast shadow.
- **Tower context:** high-rise-like building geometry, visible facade edge, repeated tower pattern, or clearly greater vertical relief than its surroundings.

Treat a strong shadow as supporting evidence, not a height measurement and never as the segmentation boundary. Sun angle, terrain, trees, and image date can all mislead.

## Exclusions

- linear road/bridge shadows;
- canal or water edges;
- tree canopies and tree shadows;
- long low-rise residential rows and warehouse roofs;
- construction sites, awnings, sports courts, and isolated dark patches;
- merged clusters when individual roofs cannot be separated.

## User-correction protocol

When the user uses **red**, it means an omitted high-rise building should be included. When the user uses **green**, it means a predicted building should be excluded. When the user uses **blue**, it means retain the building but contract its boundary away from the marked non-building area, such as a cast shadow or paved courtyard. Include or remove the actual visible building entity, never the circle shape or a cast shadow. Use one candidate per separable building. If the marking refers to an ambiguous group, keep it as `review` and show it separately rather than silently expanding the label.

## Rule-promotion gate

Record the feedback with its image identifier. A proposed visual rule becomes reusable only after the same pattern is confirmed in at least three separately reviewed TIFFs and no repeated green correction contradicts it. Until then it is an image-local correction, not a global inclusion rule.

## Confidence labels

- `high`: strong shadow plus a distinct roof and at least one corroborating cue.
- `medium`: distinct roof with a plausible shadow but incomplete separation or contextual ambiguity.
- `review`: explicit user-marked or data-supported candidate that is not visually decisive.
