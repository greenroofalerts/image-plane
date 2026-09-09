# Image reader failure and reporting incident

Verified 9 September 2026, approximately 16:43 BST. Owner: the existing Memory Spine task. This is an open incident, not a completed rebuild.

## What failed

On 8 September, three small development checks used six existing photographs from six different jobs, selected from records with at least two mapped Lee labels. The prompt contained the recovered vocabulary but no examples from those photographs or jobs. Images were converted to JPEG locally and sent only to Mini A's local Ollama service.

| Check | Usable responses | Agreement with recorded notes |
|---|---:|---|
| Qwen2.5-VL, first output format | 2 / 6 | 2 matched labels, 89 additional proposals, 2 missed labels across the two usable responses; four responses failed parsing |
| Qwen3-VL, revised constrained JSON format | 0 / 6 | No usable responses; no semantic accuracy could be measured |
| Qwen2.5-VL, revised constrained JSON format | 6 / 6 | 1 of 18 reference labels matched; 17 missed; 70 additional proposals |
| Qwen3.8-27B, same six photos and current format, 9 September | 6 / 6 | 4 of 18 reference labels matched; 14 missed; 29 additional proposals |

These are development diagnostics, not a representative acceptance benchmark. Lee's notes are not exhaustive inventories of everything visible. Additional proposals are therefore unadjudicated, not automatically proven false. Parsing success is not evidence of correct interpretation. The failures implicate the reader configuration/prompt/vocabulary/annotation path as well as possible model limitations; the precise cause has not been isolated. The newer model alone did not fix the problem.

Earlier evaluation runs overwrote their detailed results file. Their aggregate logs survive, but a complete immutable reproduction record for each earlier run was not retained. The new Qwen3.8 run preserves raw responses, source hashes, code and vocabulary hashes and the prior surviving evaluation in a separate local incident directory. Two synthetic red/blue controls through Qwen3.8's chat endpoint passed; they establish only that this endpoint distinguishes those simple images, not that the production generate endpoint or roof vocabulary is correct.

## Actual impact and containment

The production new-reading cache contains zero rows. Its two historical production model attempts both errored. The diagnostic scripts wrote separate evaluation files and did not insert their proposals into the collection cache. This was checked again after the Qwen3.8 evaluation.

The collection contains 18,688 distinct indexed photos. 18,082 source-file records await model interpretation; paths and unique photos are different denominators. Of the 6,375 distinct photos with keywords, 6,213 use historical machine proposals only, 75 combine historical machine proposals with Lee labels, and 87 have Lee labels only. These reused historical proposals have not been validated by the new tests. Keyword counts must not be described as verified new image readings.

Model calls remain disabled while source checks, exact-byte recovery and reuse continue. The last batch processing files finished at 02:56:57 BST on 9 September. A once-a-minute source check is not continued progress on the waiting image-reading backlog. No new test label was promoted to a canonical business fact by this continuation.

## Reporting failure

The failure should have been raised immediately as an incident with the impact, containment and active recovery work. A later brief mention of disabled labels was inadequate. The shared LEE-391 record stopped before the test failure. No reliable automatic notification to Lee was installed; the existing task-wakeup adapter remains null. Lee had no dependable way to learn of the stall without checking or asking.

The page also incorrectly labelled every poll's finish time as the last substantive batch. This gave a misleading impression of processing progress.

## Repairs completed in this response

- Added a persistent BLOCKED reading notice to the private collection and every generated job page, including pending work, failed comparisons, containment and the unconnected notification route.
- Separated the last source-check time from the last batch that actually processed files, using durable processing receipts.
- Corrected the displayed keyword denominator to distinct photos and described existing keywords without claiming new interpretation.
- Tested the installed Qwen3.8-27B on the same six photos; preserved the raw local evidence and kept the failed proposals isolated.
- Passed 48 targeted tests, including regressions for a fresh poll masking old progress and an absent quality record being reported as unknown.
- Installed the presentation repair in the existing worker runtime with a rollback backup. Verified the live collection warning, job-page warning, accurate timestamps, unchanged existing homepage response, and empty production reading cache. The processing code, disabled-model setting and 60-second interval are unchanged.

The existing private Image Plane collection page contains the warning.

## Remaining recovery work and acceptance

The next technical work is to isolate transport/formatting errors from keyword-selection errors, reconcile the original teaching records and their scopes, then compare the corrected reader against a broader separate sample of original annotated photos and explicit negative controls. Record unsupported proposals separately from missed approved labels. Preserve model identity, prompt, inputs and raw outputs for every evaluation. A newer model or valid JSON alone is insufficient evidence to resume bulk interpretation.

Automatic alert delivery is still unresolved. The visible warning and shared incident record improve visibility but do not prove an unattended alert reaches Lee. The existing exact-task continuation route must be connected and a deliberate failure delivered once, with acknowledgement, before it is described as working. No new scheduler that repeatedly runs a model on unchanged data has been substituted.
