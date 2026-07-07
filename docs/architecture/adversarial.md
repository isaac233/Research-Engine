# Adversarial

The adversarial layer exists to ensure that only verifiable claims reach the
main AI. It runs after extraction and before final evaluation.

## Components

- `Devil` — attacks the load-bearing assumption of every claim. Asks: what
  would make this claim false? Is the source actually saying this? Is the
  evidence cherry-picked?
- `Verifier` — independently re-fetches or re-checks the source for each
  challenged claim.
- `ChallengeDispatcher` — turns devil challenges into specific verification
  tasks and routes them to the verifier.
- `URLPolicy` adversarial tests — ensure SSRF guards cannot be bypassed by
  encoding tricks or redirect chains.

## Process

```
Extracted claims → Devil challenges → Verifier checks → Pass / Fail / Downgrade
```

A claim that fails verification is either removed or downgraded and rephrased
to match the source. The brief records the original claim, the challenge, and
the resolution.

## Output

- `VerifiedClaim` — claim text, source list, confidence, challenge summary,
  resolution.
- The brief only includes claims with at least `MEDIUM` confidence after
  adversarial review.
